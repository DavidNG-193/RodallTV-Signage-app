from __future__ import annotations

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

from rodall_signage.player.mpv_controller import MpvController


class MainWindow(QMainWindow):
    def __init__(self, media_path: Path | None, windowed: bool) -> None:
        super().__init__()

        self._media_path = media_path
        self._windowed = windowed
        self._player_started = False
        self._player = MpvController(self)

        self.setWindowTitle("RodallTV Signage Prototype")
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
            "TASAS DEL DÍA     USD / MXN --.--     EUR / MXN --.--     GBP / MXN --.--"
        )
        self._rates_bar.setObjectName("ratesBar")
        self._rates_bar.setFixedHeight(42)
        self._rates_bar.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

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
        weather_layout.addWidget(self._body("Sin información del clima"))

        references_card = QFrame()
        references_card.setObjectName("card")
        references_layout = QVBoxLayout(references_card)
        references_layout.addWidget(self._title("REFERENCIAS DEL DÍA"))
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

        self._status_label = QLabel("Preparando mpv...")
        self._status_label.setObjectName("statusBar")
        self._status_label.setFixedHeight(28)

        root_layout.addWidget(self._rates_bar)
        root_layout.addWidget(content, 1)
        root_layout.addWidget(self._status_label)

        self.setCentralWidget(root)

    def _connect_signals(self) -> None:
        self._player.ready.connect(self._on_player_ready)
        self._player.error_occurred.connect(self._show_error)
        self._player.playback_event.connect(self._on_playback_event)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)

        if self._player_started:
            return

        self._player_started = True

        # Esperar a que Qt cree el identificador nativo del contenedor.
        QTimer.singleShot(0, self._start_player)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._status_label.setText("Cerrando mpv...")
        self._player.stop()
        event.accept()

    def _start_player(self) -> None:
        window_id = int(self._video_frame.winId())
        self._player.start(window_id)

    def _on_player_ready(self) -> None:
        self._status_label.setText("mpv conectado mediante JSON IPC.")

        if self._media_path is not None:
            self._player.load(self._media_path)

    def _on_playback_event(self, event: dict) -> None:
        if event.get("event") == "property-change" and event.get("name") == "path":
            current_path = event.get("data")
            if current_path:
                self._status_label.setText(f"Reproduciendo: {current_path}")

        if event.get("event") == "end-file":
            self._status_label.setText("El archivo terminó.")

    def _show_error(self, message: str) -> None:
        self._status_label.setText(message)
        print(f"[RodallTV] {message}")

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

        QFrame#card {
            background: #0d192c;
            border: 1px solid #263956;
            border-radius: 12px;
        }

        QLabel#cardTitle {
            color: #afc2df;
            font-size: 13px;
            font-weight: 700;
        }

        QLabel#cardValue {
            color: white;
            font-size: 36px;
            font-weight: 700;
        }

        QLabel#cardBody {
            color: #d4deed;
            font-size: 13px;
        }

        QLabel#statusBar {
            background: #0b1424;
            color: #9fb0c8;
            padding-left: 12px;
            border-top: 1px solid #26334a;
        }
        """