from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

logger = logging.getLogger(__name__)


class ExchangeRateWorkerSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)


class ExchangeRateFetchWorker(QRunnable):
    def __init__(self, api_client: Any) -> None:
        super().__init__()
        self._api_client = api_client
        self.signals = ExchangeRateWorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            payload = self._api_client.get_exchange_rates()
            self.signals.succeeded.emit(payload)
        except Exception as exc:
            logger.exception("Falló la actualización de tasas.")
            self.signals.failed.emit(str(exc))