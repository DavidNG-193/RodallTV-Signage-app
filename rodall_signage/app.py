from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from rodall_signage.bootstrap import (
    build_context,
    install_exception_hook,
)
from rodall_signage.config import AppSettings
from rodall_signage.ui.main_window import MainWindow


logger = logging.getLogger(__name__)


def run() -> int:
    arguments = _parse_arguments()
    settings = AppSettings.from_environment()

    media_path = _resolve_media_path(
        arguments.media,
        settings.test_media_path,
    )

    windowed = arguments.windowed or settings.windowed

    app = QApplication(sys.argv)
    app.setApplicationName(settings.app_name)
    app.setQuitOnLastWindowClosed(False)

    context = build_context(settings)
    install_exception_hook(app, context.event_bus)

    window = MainWindow(
        context=context,
        media_path=media_path,
        playlist_path=arguments.playlist,
    )

    context.lifecycle.shutdown_completed.connect(app.quit)

    if windowed:
        window.resize(1280, 720)
        window.show()
    else:
        window.showFullScreen()

    exit_code = app.exec()

    context.lifecycle.shutdown()

    logger.info(
        "Proceso principal finalizado. exit_code=%s",
        exit_code,
    )
    return exit_code


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="RodallTV Signage"
    )

    parser.add_argument(
        "--media",
        type=Path,
        help="Archivo local para prueba.",
    )

    parser.add_argument(
        "--windowed",
        action="store_true",
        help="Ejecutar en ventana.",
    )

    parser.add_argument(
        "--playlist",
        type=Path,
        help="Archivo JSON de playlist local.",
    )

    return parser.parse_args()


def _resolve_media_path(
    argument_path: Path | None,
    configured_path: Path | None,
) -> Path | None:
    selected = argument_path or configured_path

    if selected is None:
        return None

    return selected.expanduser().resolve()
