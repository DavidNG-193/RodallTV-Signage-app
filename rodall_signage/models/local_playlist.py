from __future__ import annotations

from dataclasses import dataclass

from rodall_signage.models.media_item import MediaItem


@dataclass(frozen=True, slots=True)
class LocalPlaylist:
    id: str
    name: str
    version: int
    items: tuple[MediaItem, ...]

    def validate(self) -> None:
        if not self.id.strip():
            raise ValueError("LocalPlaylist.id es obligatorio.")

        if not self.name.strip():
            raise ValueError("LocalPlaylist.name es obligatorio.")

        if self.version <= 0:
            raise ValueError(
                "LocalPlaylist.version debe ser mayor que cero."
            )

        if not self.items:
            raise ValueError(
                "La playlist debe contener al menos un elemento."
            )

        for item in self.items:
            # La existencia se comprueba al reproducir para poder omitir un
            # archivo faltante sin descartar toda la playlist.
            item.validate(require_file=False)
