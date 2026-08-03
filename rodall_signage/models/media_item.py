from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class MediaKind(StrEnum):
    IMAGE = "Image"
    VIDEO = "Video"


@dataclass(frozen=True, slots=True)
class MediaItem:
    id: str
    path: Path
    kind: MediaKind
    duration_seconds: int | None = None

    def validate(self) -> None:
        if not self.id.strip():
            raise ValueError("MediaItem.id es obligatorio.")

        if not self.path.is_file():
            raise ValueError(f"No existe el archivo multimedia: {self.path}")

        if (
            self.kind == MediaKind.IMAGE
            and self.duration_seconds is not None
            and self.duration_seconds <= 0
        ):
            raise ValueError(
                "La duración de una imagen debe ser mayor que cero."
            )