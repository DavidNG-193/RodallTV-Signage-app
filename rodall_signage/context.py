from __future__ import annotations

from dataclasses import dataclass

from rodall_signage.api.device_api_client import DeviceApiClient
from rodall_signage.cache.cache_registry import CacheRegistry
from rodall_signage.config import AppSettings
from rodall_signage.events import AppEventBus
from rodall_signage.player.mpv_controller import MpvController
from rodall_signage.player.playback_coordinator import PlaybackCoordinator
from rodall_signage.services.lifecycle_service import LifecycleService
from rodall_signage.services.cache_demo_service import CacheDemoService
from rodall_signage.services.heartbeat_service import HeartbeatService
from rodall_signage.services.exchange_rate_update_service import (
    ExchangeRateUpdateService,
)
from rodall_signage.services.local_playlist_loader import LocalPlaylistLoader
from rodall_signage.services.weather_update_service import WeatherUpdateService
from rodall_signage.sync.content_store import ContentStore
from rodall_signage.sync.manifest_playlist_adapter import (
    ManifestPlaylistAdapter,
)
from rodall_signage.sync.manifest_store import ManifestStore
from rodall_signage.sync.synchronization_service import SynchronizationService


@dataclass(slots=True)
class AppContext:
    settings: AppSettings
    event_bus: AppEventBus
    player: MpvController
    playback: PlaybackCoordinator
    playlist_loader: LocalPlaylistLoader
    api_client: DeviceApiClient
    manifest_store: ManifestStore
    content_store: ContentStore
    playlist_adapter: ManifestPlaylistAdapter
    synchronization: SynchronizationService
    heartbeat: HeartbeatService
    exchange_rate_update_service: ExchangeRateUpdateService
    weather_update_service: WeatherUpdateService
    cache_registry: CacheRegistry
    cache_demo: CacheDemoService
    lifecycle: LifecycleService
