from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, QThreadPool, QTimer, Signal, Slot

from rodall_signage.cache.cache_models import CacheFreshness
from rodall_signage.services.weather_parser import parse_weather_snapshot
from rodall_signage.services.weather_worker import WeatherFetchWorker


logger = logging.getLogger(__name__)


class WeatherUpdateService(QObject):
    snapshot_changed = Signal(object)
    availability_changed = Signal(str)

    def __init__(
        self,
        api_client: Any,
        store: Any,
        refresh_seconds: int,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._api_client = api_client
        self._store = store
        self._refresh_seconds = max(refresh_seconds, 300)
        self._thread_pool = QThreadPool(self)
        self._thread_pool.setMaxThreadCount(1)
        self._request_in_progress = False
        self._running = False
        self._cache_published = False

        self._timer = QTimer(self)
        self._timer.setInterval(self._refresh_seconds * 1000)
        self._timer.timeout.connect(self.refresh)

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
        self._thread_pool.clear()
        self._thread_pool.waitForDone(1000)

    @Slot()
    def refresh(self) -> None:
        if not self._running or self._request_in_progress:
            return
        self._request_in_progress = True
        worker = WeatherFetchWorker(self._api_client)
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
            snapshot = parse_weather_snapshot(payload)
            self._store.save(snapshot)
            logger.info(
                "Actualización de clima aplicada. enabled=%s stale=%s",
                snapshot.enabled,
                snapshot.is_stale,
            )
            self.snapshot_changed.emit(snapshot)
            self.availability_changed.emit(
                "stale" if snapshot.is_stale else "fresh"
            )
        except Exception:
            logger.exception("No fue posible procesar el clima recibido.")
            self._publish_cached_value()
        finally:
            self._request_in_progress = False

    @Slot(str)
    def _on_failure(self, message: str) -> None:
        if not self._running:
            self._request_in_progress = False
            return
        logger.warning(
            "No se actualizó el clima; se intentará usar caché: %s",
            message,
        )
        self._publish_cached_value()
        self._request_in_progress = False

    def _publish_cached_value(self) -> None:
        result = self._store.read()
        if result.envelope is not None:
            logger.info(
                "Caché de clima cargada. freshness=%s",
                result.freshness.value,
            )
            snapshot = result.envelope.payload
            self.snapshot_changed.emit(snapshot)
            state = result.freshness.value.lower()
            if snapshot.is_stale:
                state = "stale"
            self.availability_changed.emit(state)
            return

        if result.freshness == CacheFreshness.INVALID:
            logger.error("Caché de clima inválida: %s", result.message)
            self.availability_changed.emit("invalid")
            return

        self.availability_changed.emit("missing")
