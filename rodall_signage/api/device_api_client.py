from __future__ import annotations

import logging
from datetime import datetime, timezone
from threading import Lock, local
from typing import Any
from weakref import WeakSet

import requests

from rodall_signage.api.api_models import (
    AssignmentStatus,
    HeartbeatResult,
    SyncReport,
)
from rodall_signage.config import AppSettings


logger = logging.getLogger(__name__)


class _ThreadSessionOwner:
    """Closes a requests session when its worker thread disappears."""

    def __init__(self) -> None:
        self.session = requests.Session()
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return

        self._closed = True
        self.session.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            # Destructors may run during interpreter shutdown.
            pass


class DeviceApiClient:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._timeout = (5, 30)
        self._thread_local = local()
        self._session_owners: WeakSet[_ThreadSessionOwner] = WeakSet()
        self._sessions_lock = Lock()

    def heartbeat(self) -> HeartbeatResult:
        with self._session().post(
            self._url("/api/agent/heartbeat"),
            headers=self._headers(),
            json={"agentVersion": "signage-pyside-1.0.0"},
            timeout=self._timeout,
        ) as response:
            response.raise_for_status()
            data = response.json()

        return HeartbeatResult(
            server_time=data.get("serverTimeUtc"),
            pending_power_command=(
                data.get("pendingPowerCommand")
                if isinstance(data.get("pendingPowerCommand"), dict)
                else None
            ),
        )

    def get_assignment(self) -> AssignmentStatus:
        with self._session().get(
            self._url("/api/agent/assignment"),
            headers=self._headers(),
            timeout=self._timeout,
        ) as response:
            response.raise_for_status()
            data = response.json()

        return AssignmentStatus(
            has_assignment=bool(data.get("hasAssignment", False)),
            playlist_id=data.get("playlistId"),
            playlist_version=int(data.get("playlistVersion") or 0),
            requires_sync=bool(data.get("requiresSync", False)),
        )

    def get_manifest(self) -> dict[str, Any]:
        with self._session().get(
            self._url("/api/agent/manifest"),
            headers=self._headers(),
            timeout=self._timeout,
        ) as response:
            response.raise_for_status()
            return response.json()

    def get_exchange_rates(self) -> dict[str, Any]:
        with self._session().get(
            self._url("/api/agent/exchange-rates"),
            headers=self._headers(),
            timeout=self._timeout,
        ) as response:
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, dict):
            raise ValueError("La respuesta de tasas no es un objeto JSON.")

        return payload

    def get_weather(self) -> dict[str, Any]:
        with self._session().get(
            self._url("/api/agent/weather"),
            headers=self._headers(),
            timeout=self._timeout,
        ) as response:
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, dict):
            raise ValueError("La respuesta de clima no es un objeto JSON.")

        return payload

    def get_references(self) -> dict[str, Any]:
        with self._session().get(
            self._url("/api/agent/references"),
            headers=self._headers(),
            timeout=self._timeout,
        ) as response:
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, dict):
            raise ValueError(
                "La respuesta de referencias no es un objeto JSON."
            )

        return payload

    def download(self, download_url: str) -> requests.Response:
        response = self._session().get(
            self._absolute_or_relative(download_url),
            headers=self._headers(),
            stream=True,
            timeout=self._timeout,
        )
        try:
            response.raise_for_status()
        except Exception:
            response.close()
            raise

        return response

    def report_sync(self, report: SyncReport) -> None:
        with self._session().post(
            self._url("/api/agent/sync-report"),
            headers=self._headers(),
            json={
                "result": report.result.value,
                "playlistId": report.playlist_id,
                "syncedVersion": report.synced_version,
                "startedAt": self._to_utc_iso(report.started_at),
                "finishedAt": self._to_utc_iso(report.finished_at),
                "message": report.message,
                "downloadedFilesCount": report.downloaded_files_count,
                "deletedFilesCount": report.deleted_files_count,
            },
            timeout=self._timeout,
        ) as response:
            response.raise_for_status()

    def acknowledge_power_command(self, command_id: str) -> None:
        if not command_id.strip():
            raise ValueError("El identificador del comando es obligatorio.")

        with self._session().post(
            self._url("/api/agent/power-command/acknowledge"),
            headers=self._headers(),
            json={"commandId": command_id},
            timeout=self._timeout,
        ) as response:
            response.raise_for_status()

    def close(self) -> None:
        with self._sessions_lock:
            owners = tuple(self._session_owners)
            self._session_owners.clear()

        for owner in owners:
            owner.close()

    def _session(self) -> requests.Session:
        session = getattr(self._thread_local, "session", None)

        if session is None:
            owner = _ThreadSessionOwner()
            session = owner.session
            self._thread_local.owner = owner
            self._thread_local.session = session
            with self._sessions_lock:
                self._session_owners.add(owner)

        return session

    def _headers(self) -> dict[str, str]:
        if not self._settings.device_id:
            raise ValueError("RODALL_DEVICE_ID no está configurado.")

        if not self._settings.device_token:
            raise ValueError("RODALL_DEVICE_TOKEN no está configurado.")

        return {
            "X-Device-Id": self._settings.device_id,
            "X-Device-Token": self._settings.device_token,
            "Accept": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self._settings.api_base_url}{path}"

    def _absolute_or_relative(self, url: str) -> str:
        if url.startswith("http://") or url.startswith("https://"):
            return url

        if not url.startswith("/"):
            url = f"/{url}"

        return self._url(url)

    @staticmethod
    def _to_utc_iso(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)

        return (
            value.astimezone(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
