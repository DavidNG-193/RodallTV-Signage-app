from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from rodall_signage.models import MediaItem


class PlaybackState(StrEnum):
    IDLE = "Idle"
    LOADING = "Loading"
    PLAYING = "Playing"
    WAITING_IMAGE = "WaitingImage"
    ERROR = "Error"
    STOPPED = "Stopped"


@dataclass(frozen=True, slots=True)
class PlaybackSnapshot:
    state: PlaybackState
    playlist_id: str | None
    playlist_version: int | None
    current_index: int | None
    total_items: int
    current_item: MediaItem | None
    message: str