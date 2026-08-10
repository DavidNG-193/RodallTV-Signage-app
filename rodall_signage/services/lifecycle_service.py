from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

from rodall_signage.api.device_api_client import DeviceApiClient
from rodall_signage.events import AppEventBus
from rodall_signage.models import AppState
from rodall_signage.player.mpv_controller import MpvController
from rodall_signage.player.playback_coordinator import PlaybackCoordinator
from rodall_signage.services.heartbeat_service import HeartbeatService
from rodall_signage.services.exchange_rate_update_service import (
    ExchangeRateUpdateService,
)
from rodall_signage.services.weather_update_service import WeatherUpdateService
from rodall_signage.sync.synchronization_service import SynchronizationService


logger = logging.getLogger(__name__)


class LifecycleService(QObject):
    shutdown_completed = Signal()

    def __init__(
        self,
        event_bus: AppEventBus,
        player: MpvController,
        playback: PlaybackCoordinator,
        api_client: DeviceApiClient,
        synchronization: SynchronizationService,
        heartbeat: HeartbeatService,
        exchange_rate_update_service: ExchangeRateUpdateService,
        weather_update_service: WeatherUpdateService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self._event_bus = event_bus
        self._player = player
        self._playback = playback
        self._api_client = api_client
        self._synchronization = synchronization
        self._heartbeat = heartbeat
        self._exchange_rate_update_service = exchange_rate_update_service
        self._weather_update_service = weather_update_service
        self._is_shutting_down = False

    def mark_starting(self) -> None:
        logger.info("Iniciando ciclo de vida.")
        self._event_bus.publish_state(AppState.STARTING)
        self._event_bus.publish_status("Iniciando aplicación...")

    def mark_ready(self) -> None:
        logger.info("Aplicación lista.")
        self._event_bus.publish_state(AppState.READY)
        self._event_bus.publish_status("Aplicación lista.")

    def mark_degraded(self, message: str) -> None:
        logger.warning("Modo degradado: %s", message)
        self._event_bus.publish_state(AppState.DEGRADED)
        self._event_bus.publish_status(message)

    def shutdown(self) -> None:
        if self._is_shutting_down:
            return

        self._is_shutting_down = True

        logger.info("Cierre controlado solicitado.")
        self._event_bus.publish_state(AppState.STOPPING)
        self._event_bus.publish_status("Cerrando aplicación...")

        operations = (
            ("clima", self._weather_update_service.stop),
            ("tasas de cambio", self._exchange_rate_update_service.stop),
            ("heartbeat", self._heartbeat.stop),
            ("sincronización", self._synchronization.stop),
            ("reproducción", self._playback.stop),
            ("mpv", self._player.stop),
            ("cliente API", self._api_client.close),
        )

        try:
            for name, operation in operations:
                try:
                    operation()
                except Exception:
                    logger.exception("Falló el cierre de %s.", name)
        finally:
            self._event_bus.publish_state(AppState.STOPPED)
            self.shutdown_completed.emit()
            logger.info("Cierre controlado completado.")
