from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from rodall_signage.models import AppState


class AppEventBus(QObject):
    app_state_changed = Signal(AppState)
    status_message_changed = Signal(str)
    fatal_error = Signal(str)
    shutdown_requested = Signal()

    def publish_state(self, state: AppState) -> None:
        self.app_state_changed.emit(state)

    def publish_status(self, message: str) -> None:
        self.status_message_changed.emit(message)

    def publish_fatal_error(self, message: str) -> None:
        self.fatal_error.emit(message)

    def request_shutdown(self) -> None:
        self.shutdown_requested.emit()