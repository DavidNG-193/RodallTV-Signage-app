from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from rodall_signage.api.api_models import HeartbeatResult
from rodall_signage.api.device_api_client import DeviceApiClient


logger = logging.getLogger(__name__)


class _HeartbeatWorker(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    power_command_acknowledged = Signal(str)
    power_command_failed = Signal(str)

    def __init__(self, api_client: DeviceApiClient) -> None:
        super().__init__()
        self._api_client = api_client

    @Slot()
    def send(self) -> None:
        try:
            self.succeeded.emit(self._api_client.heartbeat())
        except Exception as error:
            message = str(error) or type(error).__name__
            logger.warning("Heartbeat fallido: %s", message)
            self.failed.emit(message)

    @Slot(object)
    def acknowledge_power_command(self, command: object) -> None:
        if not isinstance(command, dict):
            self.power_command_failed.emit(
                "El comando de energía recibido no es válido."
            )
            return

        command_id = str(command.get("commandId", "")).strip()
        command_type = str(command.get("commandType", "")).strip()
        if not command_id or command_type not in {"Restart", "Shutdown"}:
            self.power_command_failed.emit(
                "El comando de energía recibido no es válido."
            )
            return

        try:
            self._api_client.acknowledge_power_command(command_id)
            self.power_command_acknowledged.emit(command_type)
        except Exception as error:
            message = str(error) or type(error).__name__
            logger.warning(
                "No fue posible confirmar el comando de energía: %s",
                message,
            )
            self.power_command_failed.emit(message)


class HeartbeatService(QObject):
    heartbeat_ok = Signal(object)
    heartbeat_failed = Signal(str)
    power_command_ready = Signal(str)
    power_command_failed = Signal(str)
    _heartbeat_requested = Signal()
    _power_command_requested = Signal(object)

    def __init__(
        self,
        api_client: DeviceApiClient,
        interval_seconds: int,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._in_progress = False
        self._power_command_in_progress = False
        self._stopping = False
        self._timer = QTimer(self)
        self._timer.setInterval(max(interval_seconds, 10) * 1000)
        self._timer.timeout.connect(self.send_now)

        self._thread = QThread(self)
        self._thread.setObjectName("rodall-heartbeat")
        self._worker = _HeartbeatWorker(api_client)
        self._worker.moveToThread(self._thread)
        self._heartbeat_requested.connect(self._worker.send)
        self._power_command_requested.connect(
            self._worker.acknowledge_power_command
        )
        self._worker.succeeded.connect(self._on_succeeded)
        self._worker.failed.connect(self._on_failed)
        self._worker.power_command_acknowledged.connect(
            self._on_power_command_acknowledged
        )
        self._worker.power_command_failed.connect(
            self._on_power_command_failed
        )

    def start(self) -> None:
        self._stopping = False
        if not self._thread.isRunning():
            self._thread.start()
        if not self._timer.isActive():
            self._timer.start()
        self.send_now()

    def stop(self) -> None:
        self._stopping = True
        self._timer.stop()
        self._in_progress = False
        self._power_command_in_progress = False

        if self._thread.isRunning():
            self._thread.requestInterruption()
            self._thread.quit()
            if not self._thread.wait(35000):
                logger.error("El hilo de heartbeat no terminó dentro del plazo.")

    @Slot()
    def send_now(self) -> None:
        if self._stopping or self._in_progress:
            return
        if not self._thread.isRunning():
            self._thread.start()

        self._in_progress = True
        self._heartbeat_requested.emit()

    @Slot(object)
    def _on_succeeded(self, result: HeartbeatResult) -> None:
        self._in_progress = False
        if self._stopping:
            return
        self.heartbeat_ok.emit(result)

        if (
            result.pending_power_command is not None
            and not self._power_command_in_progress
        ):
            self._power_command_in_progress = True
            self._timer.stop()
            self._power_command_requested.emit(result.pending_power_command)

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self._in_progress = False
        if self._stopping:
            return
        self.heartbeat_failed.emit(message)

    @Slot(str)
    def _on_power_command_acknowledged(self, command_type: str) -> None:
        if self._stopping:
            return
        self.power_command_ready.emit(command_type)

    @Slot(str)
    def _on_power_command_failed(self, message: str) -> None:
        self._power_command_in_progress = False
        if self._stopping:
            return
        if not self._timer.isActive():
            self._timer.start()
        self.power_command_failed.emit(message)
