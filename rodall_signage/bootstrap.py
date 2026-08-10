from __future__ import annotations

import logging
import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox

from rodall_signage.api.device_api_client import DeviceApiClient
from rodall_signage.cache.cache_registry import CacheRegistry
from rodall_signage.config import AppSettings
from rodall_signage.context import AppContext
from rodall_signage.events import AppEventBus
from rodall_signage.logging_config import configure_logging
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
from rodall_signage.stores.exchange_rate_store import ExchangeRateStore
from rodall_signage.stores.reference_store import ReferenceStore
from rodall_signage.stores.weather_store import WeatherStore


logger = logging.getLogger(__name__)


def build_context(settings: AppSettings) -> AppContext:
    settings.ensure_directories()
    log_file = configure_logging(settings.log_dir, settings.log_level)

    logger.info("========================================")
    logger.info("Arranque de %s", settings.app_name)
    logger.info("Entorno: %s", settings.environment)
    logger.info("Log: %s", log_file)
    logger.info("mpv: %s", settings.mpv_executable)

    event_bus = AppEventBus()
    player = MpvController(settings=settings)
    playback = PlaybackCoordinator(player=player)
    playlist_loader = LocalPlaylistLoader()
    api_client = DeviceApiClient(settings=settings)
    manifest_store = ManifestStore(settings.manifest_path)
    content_store = ContentStore(settings.content_dir)
    playlist_adapter = ManifestPlaylistAdapter(content_store)
    synchronization = SynchronizationService(
        api_client=api_client,
        manifest_store=manifest_store,
        content_store=content_store,
        playlist_adapter=playlist_adapter,
        playback=playback,
        interval_seconds=settings.sync_seconds,
    )
    heartbeat = HeartbeatService(
        api_client=api_client,
        interval_seconds=settings.heartbeat_seconds,
    )
    cache_registry = CacheRegistry(
        exchange_rates=ExchangeRateStore(
            settings.cache_dir / "exchange_rates.json"
        ),
        weather=WeatherStore(settings.cache_dir / "weather.json"),
        references=ReferenceStore(settings.cache_dir / "references.json"),
    )
    cache_demo = CacheDemoService(cache_registry)
    exchange_rate_update_service = ExchangeRateUpdateService(
        api_client=api_client,
        store=cache_registry.exchange_rates,
        refresh_seconds=settings.exchange_rate_refresh_seconds,
    )
    weather_update_service = WeatherUpdateService(
        api_client=api_client,
        store=cache_registry.weather,
        refresh_seconds=settings.weather_refresh_seconds,
    )
    lifecycle = LifecycleService(
        event_bus=event_bus,
        player=player,
        playback=playback,
        api_client=api_client,
        synchronization=synchronization,
        heartbeat=heartbeat,
        exchange_rate_update_service=exchange_rate_update_service,
        weather_update_service=weather_update_service,
    )

    return AppContext(
        settings=settings,
        event_bus=event_bus,
        player=player,
        playback=playback,
        playlist_loader=playlist_loader,
        api_client=api_client,
        manifest_store=manifest_store,
        content_store=content_store,
        playlist_adapter=playlist_adapter,
        synchronization=synchronization,
        heartbeat=heartbeat,
        exchange_rate_update_service=exchange_rate_update_service,
        weather_update_service=weather_update_service,
        cache_registry=cache_registry,
        cache_demo=cache_demo,
        lifecycle=lifecycle,
    )


def install_exception_hook(
    app: QApplication,
    event_bus: AppEventBus,
) -> None:
    def handle_exception(
        exception_type: type,
        exception_value: BaseException,
        exception_traceback: object,
    ) -> None:
        if issubclass(exception_type, KeyboardInterrupt):
            sys.__excepthook__(
                exception_type,
                exception_value,
                exception_traceback,
            )
            return

        formatted = "".join(
            traceback.format_exception(
                exception_type,
                exception_value,
                exception_traceback,
            )
        )

        logger.critical("Excepción no controlada:\n%s", formatted)

        message = (
            "RodallTV encontró un error no controlado. "
            "Consulta runtime/logs/rodall-signage.log."
        )

        event_bus.publish_fatal_error(message)

        if QApplication.activeWindow() is not None:
            QMessageBox.critical(
                QApplication.activeWindow(),
                "Error de RodallTV",
                message,
            )

        app.quit()

    sys.excepthook = handle_exception
