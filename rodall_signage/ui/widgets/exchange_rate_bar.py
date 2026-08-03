from __future__ import annotations

from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QWidget,
)

from rodall_signage.models import ExchangeRate, RateTrend


class ExchangeRateBar(QFrame):
    _REPEAT_COUNT = 6

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("exchangeRateBar")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._rates: list[ExchangeRate] = []
        self._offset = 0
        self._cycle_width = 0
        self._track: QWidget | None = None
        self._first_group: QWidget | None = None

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._viewport = QWidget()
        self._viewport.setObjectName("ratesViewport")
        self._viewport.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._viewport.setAttribute(Qt.WA_StyledBackground, True)
        self._viewport.installEventFilter(self)
        root_layout.addWidget(self._viewport)

        self._scroll_timer = QTimer(self)
        self._scroll_timer.setInterval(24)
        self._scroll_timer.timeout.connect(self._advance_ticker)

        self.set_rates([])

    def set_rates(self, rates: list[ExchangeRate]) -> None:
        self._scroll_timer.stop()
        self._rates = list(rates)
        self._offset = 0
        self._cycle_width = 0
        self._first_group = None

        if self._track is not None:
            self._track.hide()
            self._track.deleteLater()

        self._track = QWidget(self._viewport)
        self._track.setObjectName("ratesTrack")
        track_layout = QHBoxLayout(self._track)
        track_layout.setContentsMargins(20, 0, 20, 0)
        track_layout.setSpacing(34)

        if not self._rates:
            empty = QLabel("Sin tasas disponibles")
            empty.setObjectName("emptyState")
            track_layout.addWidget(empty)
            self._track.adjustSize()
            self._position_track()
            return

        first_group = self._build_rates_group()
        self._first_group = first_group
        track_layout.addWidget(first_group)

        for _ in range(self._REPEAT_COUNT - 1):
            track_layout.addWidget(self._build_rates_group())

        track_layout.activate()
        self._track.adjustSize()
        self._position_track()
        QTimer.singleShot(0, self._start_scrolling)

    def set_bar_height(self, height: int) -> None:
        self.setFixedHeight(height)
        self._position_track()

    def eventFilter(self, watched: object, event: QEvent) -> bool:
        if watched is self._viewport and event.type() == QEvent.Resize:
            self._position_track()
        return super().eventFilter(watched, event)

    def _build_rates_group(self) -> QWidget:
        group = QWidget()
        group.setObjectName("ratesGroup")
        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(30)

        for rate in self._rates:
            entry = QWidget()
            entry.setObjectName("rateEntry")
            entry_layout = QHBoxLayout(entry)
            entry_layout.setContentsMargins(0, 0, 0, 0)
            entry_layout.setSpacing(9)

            symbol = QLabel(rate.label)
            symbol.setObjectName("rateSymbol")

            value = QLabel(f"{rate.value:,.2f}")
            value.setObjectName("rateValue")

            arrow = {
                RateTrend.UP: "▲",
                RateTrend.DOWN: "▼",
                RateTrend.NEUTRAL: "•",
            }[rate.trend]
            change = QLabel(f"{arrow}  {rate.formatted_change()}")
            change.setObjectName(
                "rateUp"
                if rate.trend == RateTrend.UP
                else "rateDown"
                if rate.trend == RateTrend.DOWN
                else "rateNeutral"
            )

            entry_layout.addWidget(symbol)
            entry_layout.addWidget(value)
            entry_layout.addWidget(change)
            layout.addWidget(entry)

        return group

    def _start_scrolling(self) -> None:
        if self._track is not None and self._first_group is not None:
            layout = self._track.layout()
            if layout is not None:
                layout.activate()
                self._cycle_width = (
                    self._first_group.sizeHint().width() + layout.spacing()
                )
            self._track.adjustSize()

        self._position_track()
        if self._cycle_width > 0 and self.isVisible():
            self._scroll_timer.start()

    def _advance_ticker(self) -> None:
        if self._track is None or self._cycle_width <= 0:
            return

        self._offset = (self._offset + 1) % self._cycle_width
        self._position_track()

    def _position_track(self) -> None:
        if self._track is None:
            return

        size_hint = self._track.sizeHint()
        track_height = max(size_hint.height(), self._viewport.height())
        self._track.resize(size_hint.width(), track_height)
        y = (self._viewport.height() - track_height) // 2
        self._track.move(-self._offset, y)
