from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

from rodall_signage.events import AppEventBus
from rodall_signage.models import AppState
from rodall_signage.player.mpv_controller import MpvController


logger = logging.getLogger(__name__)


class LifecycleService(QObject):
    shutdown_completed = Signal()

    def __init__(
        self,
        event_bus: AppEventBus,
        player: MpvController,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self._event_bus = event_bus
        self._player = player
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

        try:
            self._player.stop()
        finally:
            self._event_bus.publish_state(AppState.STOPPED)
            self.shutdown_completed.emit()
            logger.info("Cierre controlado completado.")