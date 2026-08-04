from __future__ import annotations

import json
import logging
from pathlib import Path

from rodall_signage.models import MediaItem, MediaKind
from rodall_signage.models.local_playlist import LocalPlaylist


logger = logging.getLogger(__name__)


class LocalPlaylistLoader:
    def load(self, playlist_path: Path) -> LocalPlaylist:
        resolved_path = playlist_path.expanduser().resolve()

        if not resolved_path.is_file():
            raise ValueError(
                f"No existe la playlist local: {resolved_path}"
            )

        try:
            raw = json.loads(
                resolved_path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as error:
            raise ValueError(
                f"El archivo JSON es inválido: {error}"
            ) from error

        playlist = LocalPlaylist(
            id=str(raw["id"]),
            name=str(raw["name"]),
            version=int(raw["version"]),
            items=tuple(
                self._parse_item(item, resolved_path.parent)
                for item in raw["items"]
            ),
        )

        playlist.validate()

        logger.info(
            "Playlist local cargada. id=%s version=%s items=%s",
            playlist.id,
            playlist.version,
            len(playlist.items),
        )

        return playlist

    def _parse_item(
        self,
        raw: dict,
        base_directory: Path,
    ) -> MediaItem:
        raw_path = Path(str(raw["path"]))

        if not raw_path.is_absolute():
            raw_path = base_directory / raw_path

        kind = MediaKind(str(raw["kind"]))
        duration = raw.get("durationSeconds")

        return MediaItem(
            id=str(raw["id"]),
            path=raw_path.resolve(),
            kind=kind,
            duration_seconds=(
                int(duration) if duration is not None else None
            ),
        )