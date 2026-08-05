from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Generic, TypeVar

from rodall_signage.cache.cache_models import (
    CacheEnvelope,
    CacheFreshness,
    CacheReadResult,
)


logger = logging.getLogger(__name__)
T = TypeVar("T")


class JsonCacheStore(Generic[T]):
    def __init__(
        self,
        path: Path,
        schema_version: int,
        serialize_payload: Callable[[T], object],
        parse_payload: Callable[[object], T],
    ) -> None:
        self._path = path
        self._schema_version = schema_version
        self._serialize_payload = serialize_payload
        self._parse_payload = parse_payload

    @property
    def path(self) -> Path:
        return self._path

    def read(self) -> CacheReadResult[T]:
        if not self._path.is_file():
            return CacheReadResult(
                freshness=CacheFreshness.MISSING,
                envelope=None,
                message="No existe un archivo de caché.",
            )

        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise TypeError("La raíz de la caché debe ser un objeto.")

            schema_version = raw["schemaVersion"]
            if type(schema_version) is not int:
                raise TypeError("schemaVersion debe ser un entero.")

            if schema_version != self._schema_version:
                return CacheReadResult(
                    freshness=CacheFreshness.INVALID,
                    envelope=None,
                    message=(
                        "Versión de esquema incompatible. "
                        f"Esperada={self._schema_version}, "
                        f"recibida={schema_version}."
                    ),
                )

            generated_at = self._parse_datetime(raw["generatedAt"])
            expires_at = (
                self._parse_datetime(raw["expiresAt"])
                if raw.get("expiresAt")
                else None
            )
            payload = self._parse_payload(raw["payload"])

            envelope = CacheEnvelope(
                schema_version=schema_version,
                generated_at=generated_at,
                expires_at=expires_at,
                payload=payload,
            )

            return CacheReadResult(
                freshness=envelope.freshness(),
                envelope=envelope,
            )

        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            json.JSONDecodeError,
        ) as error:
            logger.error("Caché inválida en %s: %s", self._path, error)
            return CacheReadResult(
                freshness=CacheFreshness.INVALID,
                envelope=None,
                message=str(error),
            )

    def write_atomic(
        self,
        payload: T,
        generated_at: datetime,
        expires_at: datetime | None,
    ) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

        envelope = {
            "schemaVersion": self._schema_version,
            "generatedAt": self._format_datetime(generated_at),
            "expiresAt": (
                self._format_datetime(expires_at)
                if expires_at is not None
                else None
            ),
            "payload": self._serialize_payload(payload),
        }

        temporary = self._temporary_path()

        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as file:
                json.dump(envelope, file, ensure_ascii=False, indent=2)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())

            self._validate_temporary(temporary)
            os.replace(temporary, self._path)
            logger.info("Caché actualizada: %s", self._path)
        except Exception:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                logger.warning(
                    "No fue posible eliminar el temporal inválido %s.",
                    temporary,
                )
            raise

    def delete(self) -> None:
        self._path.unlink(missing_ok=True)
        self._temporary_path().unlink(missing_ok=True)

    def _validate_temporary(self, temporary: Path) -> None:
        raw = json.loads(temporary.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise TypeError("La raíz temporal debe ser un objeto.")

        if (
            type(raw.get("schemaVersion")) is not int
            or raw["schemaVersion"] != self._schema_version
        ):
            raise ValueError("El archivo temporal tiene un esquema inválido.")

        self._parse_datetime(raw["generatedAt"])

        if raw.get("expiresAt"):
            self._parse_datetime(raw["expiresAt"])

        self._parse_payload(raw["payload"])

    @staticmethod
    def _parse_datetime(value: object) -> datetime:
        if not isinstance(value, str) or not value.strip():
            raise TypeError("La fecha debe ser una cadena ISO-8601.")

        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        normalized = (
            value.replace(tzinfo=timezone.utc)
            if value.tzinfo is None
            else value.astimezone(timezone.utc)
        )
        return normalized.isoformat().replace("+00:00", "Z")

    def _temporary_path(self) -> Path:
        return self._path.with_suffix(self._path.suffix + ".tmp")
