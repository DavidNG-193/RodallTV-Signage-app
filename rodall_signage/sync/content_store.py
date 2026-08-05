from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Protocol

from rodall_signage.sync.manifest_models import ManifestItem


logger = logging.getLogger(__name__)
_CHUNK_SIZE = 1024 * 1024


class StreamingResponse(Protocol):
    def iter_content(self, chunk_size: int) -> object: ...


class ContentStore:
    def __init__(self, content_dir: Path) -> None:
        self._content_dir = content_dir
        self._content_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, item: ManifestItem) -> Path:
        item.validate()
        return self._content_dir / item.stored_file_name

    def is_valid(self, item: ManifestItem) -> bool:
        return self._is_valid_path(self.path_for(item), item)

    def save_response_atomic(
        self,
        item: ManifestItem,
        response: StreamingResponse,
    ) -> Path:
        destination = self.path_for(item)
        temporary = destination.with_suffix(destination.suffix + ".part")
        temporary.parent.mkdir(parents=True, exist_ok=True)

        try:
            with temporary.open("wb") as file:
                for chunk in response.iter_content(chunk_size=_CHUNK_SIZE):
                    if chunk:
                        file.write(chunk)
                file.flush()
                os.fsync(file.fileno())

            if not self._is_valid_path(temporary, item):
                raise ValueError(
                    f"{item.original_file_name} no coincide en tamaño o SHA-256."
                )

            os.replace(temporary, destination)
            return destination
        except Exception:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                logger.warning("No fue posible eliminar %s.", temporary)
            raise

    def delete_obsolete(self, valid_names: set[str]) -> int:
        deleted = 0

        for path in self._content_dir.iterdir():
            if (
                not path.is_file()
                or path.name == ".gitkeep"
                or path.name in valid_names
            ):
                continue

            try:
                path.unlink()
                deleted += 1
            except OSError:
                logger.warning("No fue posible eliminar el obsoleto %s.", path)

        return deleted

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for block in iter(lambda: file.read(_CHUNK_SIZE), b""):
                digest.update(block)
        return digest.hexdigest().lower()

    def _is_valid_path(self, path: Path, item: ManifestItem) -> bool:
        try:
            return (
                path.is_file()
                and path.stat().st_size == item.file_size_bytes
                and self._sha256(path) == item.hash_sha256.lower()
            )
        except OSError:
            return False
