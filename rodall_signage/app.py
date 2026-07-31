from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from rodall_signage.config import APP_NAME
from rodall_signage.ui.main_window import MainWindow


def run(media_path: Path | None, windowed: bool) -> int:
    application = QApplication(sys.argv)
    application.setApplicationName(APP_NAME)

    window = MainWindow(media_path=media_path, windowed=windowed)

    if windowed:
        window.resize(1280, 720)
        window.show()
    else:
        window.showFullScreen()

    return application.exec()