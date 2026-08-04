from __future__ import annotations

from dataclasses import dataclass

from rodall_signage.config import AppSettings
from rodall_signage.events import AppEventBus
from rodall_signage.player.mpv_controller import MpvController
from rodall_signage.player.playback_coordinator import PlaybackCoordinator
from rodall_signage.services.lifecycle_service import LifecycleService
from rodall_signage.services.local_playlist_loader import LocalPlaylistLoader


@dataclass(slots=True)
class AppContext:
    settings: AppSettings
    event_bus: AppEventBus
    player: MpvController
    playback: PlaybackCoordinator
    playlist_loader: LocalPlaylistLoader
    lifecycle: LifecycleService