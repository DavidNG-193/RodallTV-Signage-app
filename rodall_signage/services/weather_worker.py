from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


logger = logging.getLogger(__name__)


class WeatherWorkerSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)


class WeatherFetchWorker(QRunnable):
    def __init__(self, api_client: Any) -> None:
        super().__init__()
        self._api_client = api_client
        self.signals = WeatherWorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.succeeded.emit(self._api_client.get_weather())
        except Exception as error:
            logger.exception("Falló la actualización del clima.")
            self.signals.failed.emit(str(error) or type(error).__name__)
