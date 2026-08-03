from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QCloseEvent, QShowEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from rodall_signage.context import AppContext
from rodall_signage.models import AppState
from rodall_signage.player.mpv_models import MpvEvent


logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(
        self,
        context: AppContext,
        media_path: Path | None,
    ) -> None:
        super().__init__()

        self._context = context
        self._media_path = media_path
        self._player_started = False
        self._allow_close = False

        self.setWindowTitle(context.settings.app_name)
        self.setMinimumSize(960, 540)
        self.setStyleSheet(self._build_stylesheet())

        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        root = QWidget(self)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._rates_bar = QLabel(
            "TASAS DEL DÍA     USD / MXN --.--     "
            "EUR / MXN --.--     GBP / MXN --.--"
        )
        self._rates_bar.setObjectName("ratesBar")
        self._rates_bar.setFixedHeight(42)
        self._rates_bar.setAlignment(
            Qt.AlignVCenter | Qt.AlignLeft
        )

        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(12)

        self._video_frame = QFrame()
        self._video_frame.setObjectName("videoFrame")
        self._video_frame.setFrameShape(QFrame.NoFrame)
        self._video_frame.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )
        self._video_frame.setAttribute(Qt.WA_NativeWindow, True)

        side_panel = QWidget()
        side_panel.setObjectName("sidePanel")
        side_panel.setMinimumWidth(270)
        side_panel.setMaximumWidth(380)

        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(12)

        weather_card = QFrame()
        weather_card.setObjectName("card")
        weather_layout = QVBoxLayout(weather_card)
        weather_layout.addWidget(self._title("Veracruz, VER"))
        weather_layout.addWidget(self._value("--°C"))
        weather_layout.addWidget(
            self._body("Sin información del clima")
        )

        references_card = QFrame()
        references_card.setObjectName("card")
        references_layout = QVBoxLayout(references_card)
        references_layout.addWidget(
            self._title("REFERENCIAS DEL DÍA")
        )
        references_layout.addWidget(
            self._body(
                "REF-0001  Referencia de demostración\n\n"
                "REF-0002  Referencia de demostración\n\n"
                "REF-0003  Referencia de demostración"
            )
        )
        references_layout.addStretch(1)

        side_layout.addWidget(weather_card, 0)
        side_layout.addWidget(references_card, 1)

        content_layout.addWidget(self._video_frame, 1)
        content_layout.addWidget(side_panel, 0)

        self._status_label = QLabel("Preparando aplicación...")
        self._status_label.setObjectName("statusBar")
        self._status_label.setFixedHeight(28)

        root_layout.addWidget(self._rates_bar)
        root_layout.addWidget(content, 1)
        root_layout.addWidget(self._status_label)

        self.setCentralWidget(root)

    def _connect_signals(self) -> None:
        self._context.player.ready.connect(
            self._on_player_ready
        )
        self._context.player.error_occurred.connect(
            self._on_player_error
        )
        self._context.player.playback_event.connect(
            self._on_playback_event
        )

        self._context.event_bus.app_state_changed.connect(
            self._on_app_state_changed
        )
        self._context.event_bus.status_message_changed.connect(
            self._status_label.setText
        )
        self._context.event_bus.fatal_error.connect(
            self._status_label.setText
        )
        self._context.event_bus.shutdown_requested.connect(
            self._context.lifecycle.shutdown
        )

        self._context.lifecycle.shutdown_completed.connect(
            self._complete_close
        )

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)

        if self._player_started:
            return

        self._player_started = True
        self._context.lifecycle.mark_starting()

        # Requisito validado para Raspberry Pi X11.
        QTimer.singleShot(250, self._start_player)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._allow_close:
            event.accept()
            return

        event.ignore()
        self._context.lifecycle.shutdown()

    def _start_player(self) -> None:
        window_id = int(self._video_frame.winId())

        if window_id <= 0:
            self._on_player_error(
                "Qt no generó un identificador válido."
            )
            return

        logger.info("Widget multimedia listo. winId=%s", window_id)
        self._context.player.start(window_id)

    def _on_player_ready(self) -> None:
        self._context.lifecycle.mark_ready()

        if self._media_path is not None:
            self._context.player.load(self._media_path)

    def _on_playback_event(self, event: MpvEvent) -> None:
        raw = event.raw or {}

        if (
            event.name == "property-change"
            and raw.get("name") == "path"
            and event.data
        ):
            self._context.event_bus.publish_status(
                f"Reproduciendo: {event.data}"
            )

        if event.name == "end-file":
            self._context.event_bus.publish_status(
                "El archivo terminó."
            )

    def _on_player_error(self, message: str) -> None:
        self._context.lifecycle.mark_degraded(message)

    def _on_app_state_changed(self, state: AppState) -> None:
        self.setProperty("appState", state.value)
        self.style().unpolish(self)
        self.style().polish(self)

    def _complete_close(self) -> None:
        self._allow_close = True
        self.close()

    @staticmethod
    def _title(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("cardTitle")
        return label

    @staticmethod
    def _value(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("cardValue")
        return label

    @staticmethod
    def _body(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("cardBody")
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        return label

    @staticmethod
    def _build_stylesheet() -> str:
        return """
        QMainWindow, QWidget {
            background: #07101f;
            color: #eef4ff;
            font-family: Arial;
        }

        QLabel#ratesBar {
            background: #111a2c;
            border-bottom: 1px solid #26334a;
            padding-left: 18px;
            font-size: 14px;
            font-weight: 700;
        }

        QFrame#videoFrame {
            background: #05080f;
            border: 1px solid #34445f;
        }

        QWidget#sidePanel {
            background: transparent;
        }

        QFrame#card {
            background: #111a2c;
            border: 1px solid #26334a;
            border-radius: 8px;
        }

        QLabel#cardTitle {
            color: #a9b7cc;
            font-size: 14px;
            font-weight: 700;
        }

        QLabel#cardValue {
            color: #ffffff;
            font-size: 42px;
            font-weight: 700;
        }

        QLabel#cardBody {
            color: #dbe7f8;
            font-size: 15px;
        }

        QLabel#statusBar {
            background: #0d1625;
            color: #9eb0c9;
            border-top: 1px solid #26334a;
            padding-left: 12px;
            font-size: 12px;
        }

        QMainWindow[appState="Degraded"] QLabel#statusBar {
            color: #ffd166;
        }
        """