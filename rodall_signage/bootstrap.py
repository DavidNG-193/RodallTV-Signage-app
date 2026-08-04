from __future__ import annotations

import logging
import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox

from rodall_signage.config import AppSettings
from rodall_signage.context import AppContext
from rodall_signage.events import AppEventBus
from rodall_signage.logging_config import configure_logging
from rodall_signage.player.mpv_controller import MpvController
from rodall_signage.player.playback_coordinator import PlaybackCoordinator
from rodall_signage.services.lifecycle_service import LifecycleService
from rodall_signage.services.local_playlist_loader import LocalPlaylistLoader


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
    lifecycle = LifecycleService(
        event_bus=event_bus,
        player=player,
        playback=playback,
    )

    return AppContext(
        settings=settings,
        event_bus=event_bus,
        player=player,
        playback=playback,
        playlist_loader=playlist_loader,
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
