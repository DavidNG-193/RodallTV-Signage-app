from __future__ import annotations

from rodall_signage.models import MediaItem, MediaKind
from rodall_signage.models.local_playlist import LocalPlaylist
from rodall_signage.sync.content_store import ContentStore
from rodall_signage.sync.manifest_models import ActiveManifest, ManifestItem


class ManifestPlaylistAdapter:
    def __init__(self, content_store: ContentStore) -> None:
        self._content_store = content_store

    def to_playlist(self, manifest: ActiveManifest) -> LocalPlaylist:
        manifest.validate()
        playlist = LocalPlaylist(
            id=manifest.playlist_id,
            name=manifest.playlist_name,
            version=manifest.playlist_version,
            items=tuple(self._to_media_item(item) for item in manifest.items),
        )
        playlist.validate()
        return playlist

    def _to_media_item(self, item: ManifestItem) -> MediaItem:
        media_type = item.media_type.strip().casefold()

        if media_type == "image":
            kind = MediaKind.IMAGE
        elif media_type == "video":
            kind = MediaKind.VIDEO
        else:
            raise ValueError(
                f"Tipo multimedia no compatible: {item.media_type}"
            )

        return MediaItem(
            id=item.playlist_item_id,
            path=self._content_store.path_for(item),
            kind=kind,
            duration_seconds=item.custom_duration_seconds,
        )
