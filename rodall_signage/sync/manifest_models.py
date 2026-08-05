from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import string


@dataclass(frozen=True, slots=True)
class ManifestItem:
    playlist_item_id: str
    media_id: str
    position: int
    original_file_name: str
    stored_file_name: str
    media_type: str
    mime_type: str
    file_size_bytes: int
    hash_sha256: str
    custom_duration_seconds: int | None
    download_url: str

    def validate(self) -> None:
        if not self.playlist_item_id.strip():
            raise ValueError("playlist_item_id es obligatorio.")
        if not self.media_id.strip():
            raise ValueError("media_id es obligatorio.")
        if self.position < 0:
            raise ValueError("position no puede ser negativo.")
        if not self.original_file_name.strip():
            raise ValueError("original_file_name es obligatorio.")
        if not self.media_type.strip():
            raise ValueError("media_type es obligatorio.")
        if not self.mime_type.strip():
            raise ValueError("mime_type es obligatorio.")
        if (
            not self.stored_file_name.strip()
            or Path(self.stored_file_name).name != self.stored_file_name
            or any(
                separator in self.stored_file_name
                for separator in ("/", "\\", ":")
            )
            or self.stored_file_name in {".", ".."}
        ):
            raise ValueError("stored_file_name no es un nombre seguro.")
        if self.file_size_bytes < 0:
            raise ValueError("file_size_bytes no puede ser negativo.")
        normalized_hash = self.hash_sha256.lower()
        if (
            len(normalized_hash) != 64
            or any(character not in string.hexdigits for character in normalized_hash)
        ):
            raise ValueError("hash_sha256 no es un SHA-256 válido.")
        if (
            self.custom_duration_seconds is not None
            and self.custom_duration_seconds <= 0
        ):
            raise ValueError(
                "custom_duration_seconds debe ser mayor que cero."
            )
        if not self.download_url.strip():
            raise ValueError("download_url es obligatorio.")


@dataclass(frozen=True, slots=True)
class ActiveManifest:
    playlist_id: str
    playlist_name: str
    playlist_version: int
    items: tuple[ManifestItem, ...]

    def validate(self) -> None:
        if not self.playlist_id.strip():
            raise ValueError("playlist_id es obligatorio.")

        if not self.playlist_name.strip():
            raise ValueError("playlist_name es obligatorio.")

        if self.playlist_version <= 0:
            raise ValueError(
                "playlist_version debe ser mayor que cero."
            )

        if not self.items:
            raise ValueError(
                "El manifiesto no contiene elementos."
            )

        positions = [item.position for item in self.items]

        if len(positions) != len(set(positions)):
            raise ValueError(
                "El manifiesto contiene posiciones duplicadas."
            )

        item_ids = [item.playlist_item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError(
                "El manifiesto contiene playlist_item_id duplicados."
            )

        stored_files: dict[str, tuple[int, str]] = {}
        for item in self.items:
            item.validate()
            signature = (item.file_size_bytes, item.hash_sha256.lower())
            previous_signature = stored_files.setdefault(
                item.stored_file_name,
                signature,
            )
            if previous_signature != signature:
                raise ValueError(
                    "Un mismo stored_file_name referencia contenidos "
                    "diferentes."
                )
