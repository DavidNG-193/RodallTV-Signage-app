from __future__ import annotations

import logging
from typing import Any, Sequence

from PySide6.QtCore import QObject, QThreadPool, QTimer, Signal, Slot

from rodall_signage.cache.cache_models import CacheFreshness

from rodall_signage.services.exchange_rate_parser import (
    parse_exchange_rate_snapshot,
)
from rodall_signage.services.exchange_rate_worker import (
    ExchangeRateFetchWorker,
)

logger = logging.getLogger(__name__)


class ExchangeRateUpdateService(QObject):
    snapshot_changed = Signal(object)
    availability_changed = Signal(str)

    def __init__(
        self,
        api_client: Any,
        store: Any,
        refresh_seconds: int,
        retry_delays_seconds: Sequence[int] = (120, 300, 900),
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self._api_client = api_client
        self._store = store
        self._refresh_seconds = max(refresh_seconds, 300)
        self._retry_delays_seconds = tuple(
            max(int(delay), 1) for delay in retry_delays_seconds
        )
        if not self._retry_delays_seconds:
            raise ValueError("Debe configurarse al menos un tiempo de reintento.")
        self._retry_attempt = 0
        self._thread_pool = QThreadPool(self)
        self._thread_pool.setMaxThreadCount(1)
        self._request_in_progress = False
        self._running = False
        self._cache_published = False

        self._timer = QTimer(self)
        self._timer.setInterval(self._refresh_seconds * 1000)
        self._timer.timeout.connect(self.refresh)

        self._retry_timer = QTimer(self)
        self._retry_timer.setSingleShot(True)
        self._retry_timer.timeout.connect(self.refresh)

    def start(self) -> None:
        if self._running:
            return

        self._running = True
        if not self._cache_published:
            self.publish_cached_value()
        self.refresh()
        self._timer.start()

    def publish_cached_value(self) -> None:
        self._publish_cached_value()
        self._cache_published = True

    def stop(self) -> None:
        self._running = False
        self._timer.stop()
        self._retry_timer.stop()
        self._thread_pool.clear()
        self._thread_pool.waitForDone(1000)

    @Slot()
    def refresh(self) -> None:
        if not self._running or self._request_in_progress:
            return

        self._retry_timer.stop()
        self._request_in_progress = True

        worker = ExchangeRateFetchWorker(self._api_client)
        worker.signals.succeeded.connect(self._on_success)
        worker.signals.failed.connect(self._on_failure)

        self._thread_pool.start(worker)

    @Slot(object)
    def _on_success(self, payload: object) -> None:
        if not self._running:
            self._request_in_progress = False
            return

        try:
            if not isinstance(payload, dict):
                raise ValueError("El endpoint devolvió un formato inválido.")

            snapshot = parse_exchange_rate_snapshot(payload)
            self._store.save(snapshot)

            logger.info(
                "Actualización de tasas aplicada. enabled=%s rates=%s stale=%s",
                snapshot.enabled,
                len(snapshot.rates),
                snapshot.is_stale,
            )
            self.snapshot_changed.emit(snapshot)
            self.availability_changed.emit(
                "stale" if snapshot.is_stale else "fresh"
            )
            if snapshot.is_stale:
                self._schedule_retry()
            else:
                self._reset_retry_schedule()
        except Exception:
            logger.exception("No fue posible procesar las tasas recibidas.")
            self._publish_cached_value()
            self._schedule_retry()
        finally:
            self._request_in_progress = False

    @Slot(str)
    def _on_failure(self, message: str) -> None:
        if not self._running:
            self._request_in_progress = False
            return

        logger.warning(
            "No se actualizaron tasas; se intentará usar caché: %s",
            message,
        )
        self._publish_cached_value()
        self._request_in_progress = False
        self._schedule_retry()

    def _schedule_retry(self) -> None:
        if not self._running:
            return

        retry_index = min(
            self._retry_attempt,
            len(self._retry_delays_seconds) - 1,
        )
        delay_seconds = self._retry_delays_seconds[retry_index]
        self._retry_attempt += 1
        self._retry_timer.start(delay_seconds * 1000)
        logger.info(
            "Siguiente reintento de tasas en %s segundos.",
            delay_seconds,
        )

    def _reset_retry_schedule(self) -> None:
        self._retry_attempt = 0
        self._retry_timer.stop()

    def _publish_cached_value(self) -> None:
        result = self._store.read()

        if result.envelope is not None:
            logger.info(
                "Caché de tasas cargada. freshness=%s",
                result.freshness.value,
            )
            self.snapshot_changed.emit(result.envelope.payload)
            state = result.freshness.value.lower()
            if result.envelope.payload.is_stale:
                state = "stale"
            self.availability_changed.emit(state)
            return

        if result.freshness == CacheFreshness.INVALID:
            logger.error("Caché de tasas inválida: %s", result.message)
            self.availability_changed.emit("invalid")
            return

        self.availability_changed.emit("missing")
