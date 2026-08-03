from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent, QResizeEvent, QShowEvent
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QVBoxLayout, QWidget

from rodall_signage.context import AppContext
from rodall_signage.models import AppState
from rodall_signage.player.mpv_models import MpvEvent
from rodall_signage.services.demo_data_service import DemoDataService
from rodall_signage.ui.responsive import LayoutMetrics, metrics_for_width
from rodall_signage.ui.theme import build_stylesheet
from rodall_signage.ui.widgets import (
    ApplicationStatusBar,
    ExchangeRateBar,
    MediaPanel,
    ReferencesPanel,
    WeatherCard,
)


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
        self._current_metrics: LayoutMetrics | None = None

        self.setWindowTitle(context.settings.app_name)
        self.setMinimumSize(960, 540)

        self._build_ui()
        self._connect_signals()
        self._load_demo_data()

    def _build_ui(self) -> None:
        self._root = QWidget(self)
        self._root_layout = QVBoxLayout(self._root)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        self._rates_bar = ExchangeRateBar()
        self._media_panel = MediaPanel()
        self._weather_card = WeatherCard()
        self._references_panel = ReferencesPanel()
        self._status_bar = ApplicationStatusBar()

        self._content = QWidget()
        self._content_layout = QHBoxLayout(self._content)

        self._side_panel = QWidget()
        self._side_layout = QVBoxLayout(self._side_panel)
        self._side_layout.setContentsMargins(0, 0, 0, 0)
        self._side_layout.addWidget(self._weather_card, 0)
        self._side_layout.addWidget(self._references_panel, 1)

        self._content_layout.addWidget(self._media_panel, 1)
        self._content_layout.addWidget(self._side_panel, 0)

        self._root_layout.addWidget(self._rates_bar)
        self._root_layout.addWidget(self._content, 1)
        self._root_layout.addWidget(self._status_bar)
        self.setCentralWidget(self._root)

    def _connect_signals(self) -> None:
        self._context.player.ready.connect(self._on_player_ready)
        self._context.player.error_occurred.connect(self._on_player_error)
        self._context.player.playback_event.connect(self._on_playback_event)
        self._context.event_bus.app_state_changed.connect(
            self._on_app_state_changed
        )
        self._context.event_bus.status_message_changed.connect(
            self._status_bar.setText
        )
        self._context.event_bus.fatal_error.connect(self._status_bar.setText)
        self._context.event_bus.shutdown_requested.connect(
            self._context.lifecycle.shutdown
        )
        self._context.lifecycle.shutdown_completed.connect(
            self._complete_close
        )

    def _load_demo_data(self) -> None:
        self._rates_bar.set_rates(DemoDataService.exchange_rates())
        self._weather_card.set_weather(DemoDataService.weather())
        self._references_panel.set_references(DemoDataService.references())

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._apply_responsive_layout(force=True)

        if self._player_started:
            return

        self._player_started = True
        self._context.lifecycle.mark_starting()
        QTimer.singleShot(250, self._start_player)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._apply_responsive_layout()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._allow_close:
            event.accept()
            return

        event.ignore()
        self._context.lifecycle.shutdown()

    def _apply_responsive_layout(self, force: bool = False) -> None:
        metrics = metrics_for_width(self.width())

        if not force and metrics == self._current_metrics:
            return

        self._current_metrics = metrics
        self.setStyleSheet(build_stylesheet(metrics))
        self._rates_bar.set_bar_height(metrics.rates_height)
        self._status_bar.set_bar_height(metrics.status_height)
        self._content_layout.setContentsMargins(
            metrics.outer_margin,
            metrics.outer_margin,
            metrics.outer_margin,
            metrics.outer_margin,
        )
        self._content_layout.setSpacing(metrics.spacing)
        self._side_layout.setSpacing(metrics.spacing)
        self._side_panel.setFixedWidth(metrics.side_width)
        self._weather_card.set_content_margins(metrics.card_padding)
        self._references_panel.set_content_margins(metrics.card_padding)

    def _start_player(self) -> None:
        window_id = self._media_panel.native_window_id()

        if window_id <= 0:
            self._on_player_error(
                "Qt no generó un identificador válido."
            )
            return

        logger.info("MediaPanel listo. winId=%s", window_id)
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
