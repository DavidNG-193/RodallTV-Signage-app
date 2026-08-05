from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from rodall_signage.sync.manifest_models import ActiveManifest, ManifestItem


logger = logging.getLogger(__name__)


class ManifestStore:
    def __init__(self, manifest_path: Path) -> None:
        self._manifest_path = manifest_path

    def load(self) -> ActiveManifest | None:
        if not self._manifest_path.is_file():
            return None

        try:
            payload = json.loads(
                self._manifest_path.read_text(encoding="utf-8")
            )
            return self.parse(payload)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            logger.exception(
                "El manifiesto activo no es válido; se conservará el archivo."
            )
            return None

    def parse(self, payload: dict[str, Any]) -> ActiveManifest:
        if payload.get("hasAssignment") is False:
            raise ValueError("El manifiesto no contiene una asignación.")

        raw_items = payload.get("items")
        if not isinstance(raw_items, list):
            raise ValueError("items debe ser una lista.")

        items = tuple(
            sorted(
                (self._parse_item(item) for item in raw_items),
                key=lambda item: item.position,
            )
        )
        manifest = ActiveManifest(
            playlist_id=self._required_string(payload, "playlistId"),
            playlist_name=self._required_string(payload, "playlistName"),
            playlist_version=int(payload["playlistVersion"]),
            items=items,
        )
        manifest.validate()
        return manifest

    def save_atomic(self, manifest: ActiveManifest) -> None:
        manifest.validate()
        self._manifest_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._manifest_path.with_suffix(
            self._manifest_path.suffix + ".tmp"
        )
        payload = self._serialize(manifest)

        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())

            os.replace(temporary, self._manifest_path)
        except Exception:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                logger.warning("No fue posible eliminar %s.", temporary)
            raise

    @staticmethod
    def _parse_item(payload: Any) -> ManifestItem:
        if not isinstance(payload, dict):
            raise TypeError("Cada elemento del manifiesto debe ser un objeto.")

        duration = payload.get("customDurationSeconds")
        return ManifestItem(
            playlist_item_id=ManifestStore._required_string(
                payload,
                "playlistItemId",
            ),
            media_id=ManifestStore._required_string(payload, "mediaId"),
            position=int(payload["position"]),
            original_file_name=ManifestStore._required_string(
                payload,
                "originalFileName",
            ),
            stored_file_name=ManifestStore._required_string(
                payload,
                "storedFileName",
            ),
            media_type=ManifestStore._required_string(payload, "mediaType"),
            mime_type=ManifestStore._required_string(payload, "mimeType"),
            file_size_bytes=int(payload["fileSizeBytes"]),
            hash_sha256=str(payload["hashSha256"]).lower(),
            custom_duration_seconds=(
                int(duration) if duration is not None else None
            ),
            download_url=ManifestStore._required_string(
                payload,
                "downloadUrl",
            ),
        )

    @staticmethod
    def _required_string(payload: dict[str, Any], key: str) -> str:
        value = payload[key]
        if value is None or not str(value).strip():
            raise ValueError(f"{key} es obligatorio.")
        return str(value).strip()

    @staticmethod
    def _serialize(manifest: ActiveManifest) -> dict[str, Any]:
        return {
            "hasAssignment": True,
            "playlistId": manifest.playlist_id,
            "playlistName": manifest.playlist_name,
            "playlistVersion": manifest.playlist_version,
            "requiresSync": False,
            "items": [
                {
                    "playlistItemId": item.playlist_item_id,
                    "mediaId": item.media_id,
                    "position": item.position,
                    "originalFileName": item.original_file_name,
                    "storedFileName": item.stored_file_name,
                    "mediaType": item.media_type,
                    "mimeType": item.mime_type,
                    "fileSizeBytes": item.file_size_bytes,
                    "hashSha256": item.hash_sha256.lower(),
                    "customDurationSeconds": item.custom_duration_seconds,
                    "downloadUrl": item.download_url,
                }
                for item in manifest.items
            ],
        }
