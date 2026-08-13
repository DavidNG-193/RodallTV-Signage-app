from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import QElapsedTimer, QEvent, QTimer, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QWidget,
)

from rodall_signage.models import ExchangeRate, ExchangeRateSnapshot


class ExchangeRateBar(QFrame):
    _REPEAT_COUNT = 6
    _FRAME_INTERVAL_MS = 33
    _SCROLL_SPEED_PX_PER_SECOND = 1000 / 24
    _MONTHS = (
        "ENE",
        "FEB",
        "MAR",
        "ABR",
        "MAY",
        "JUN",
        "JUL",
        "AGO",
        "SEP",
        "OCT",
        "NOV",
        "DIC",
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("exchangeRateBar")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._rates: list[ExchangeRate] = []
        self._snapshot: ExchangeRateSnapshot | None = None
        self._cache_state = "missing"
        self._offset = 0.0
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

        self._effective_date = QLabel("Consultado: --\nBANXICO --")
        self._effective_date.setObjectName("rateStaticDate")
        self._effective_date.setAlignment(Qt.AlignCenter)
        self._effective_date.setMinimumWidth(165)
        self._effective_date.setSizePolicy(
            QSizePolicy.Fixed,
            QSizePolicy.Expanding,
        )
        root_layout.addWidget(self._effective_date)

        self._scroll_timer = QTimer(self)
        self._scroll_timer.setInterval(self._FRAME_INTERVAL_MS)
        self._scroll_timer.setTimerType(Qt.PreciseTimer)
        self._scroll_timer.timeout.connect(self._advance_ticker)
        self._scroll_clock = QElapsedTimer()

        self.show_empty_state()

    def set_snapshot(self, snapshot: ExchangeRateSnapshot) -> None:
        self._snapshot = snapshot
        if not snapshot.enabled:
            self._rates = []
            self._effective_date.setText("Consultado: --\nBANXICO --")
            self._replace_track("Sin tasas configuradas")
            return

        self.set_rates(list(snapshot.rates))

    def set_cache_state(self, state: str) -> None:
        normalized = state.strip().lower()
        self._cache_state = normalized

        if normalized in {"missing", "invalid"} and not self._rates:
            self.show_empty_state()
            return

        if self._rates:
            self.set_rates(self._rates)

    def show_empty_state(self) -> None:
        self._snapshot = None
        self._rates = []
        self._effective_date.setText("Consultado: --\nBANXICO --")
        self._replace_track("Tasas no disponibles")

    def set_rates(self, rates: list[ExchangeRate]) -> None:
        self._rates = sorted(rates, key=lambda rate: rate.position)
        if not self._rates:
            self._effective_date.setText("Consultado: --\nBANXICO --")
            self._replace_track("Tasas no disponibles")
            return

        latest_date = max(rate.effective_date for rate in self._rates)
        self._effective_date.setText(
            f"{self._format_updated_at()}\n"
            f"BANXICO {latest_date.day:02d} "
            f"{self._MONTHS[latest_date.month - 1]}."
        )

        self._replace_track()

    def _format_updated_at(self) -> str:
        fetched_at = (
            self._snapshot.fetched_at_utc
            if self._snapshot is not None
            else None
        )
        if fetched_at is None:
            return "Consultado: --"

        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        local_time = fetched_at.astimezone()
        if local_time.date() == datetime.now().astimezone().date():
            return f"Consultado: hoy {local_time:%H:%M}"

        month = self._MONTHS[local_time.month - 1]
        return f"Consultado: {local_time.day:02d} {month}. {local_time:%H:%M}"

    def _replace_track(self, empty_message: str | None = None) -> None:
        self._scroll_timer.stop()
        self._scroll_clock.invalidate()
        self._offset = 0.0
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

        if empty_message is not None:
            empty = QLabel(empty_message)
            empty.setObjectName("emptyState")
            track_layout.addWidget(empty)
            self._track.adjustSize()
            self._position_track()
            self._track.show()
            self._track.raise_()
            return

        first_group = self._build_rates_group()
        self._first_group = first_group
        track_layout.addWidget(first_group)
        for _ in range(self._REPEAT_COUNT - 1):
            track_layout.addWidget(self._build_rates_group())

        track_layout.activate()
        self._track.adjustSize()
        self._position_track()
        # La pista no está administrada por un layout porque se desplaza con
        # move(). Si se crea después de mostrar la ventana, Qt la deja oculta
        # hasta que se llama show() explícitamente.
        self._track.show()
        self._track.raise_()
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

            symbol = QLabel(rate.display_name)
            symbol.setObjectName("rateSymbol")
            value = QLabel(rate.formatted_value())
            value.setObjectName("rateValue")

            if rate.change_percent is None:
                arrow = "•"
                change_object_name = "rateNeutral"
            elif rate.change_percent > 0:
                arrow = "▲"
                change_object_name = "rateUp"
            elif rate.change_percent < 0:
                arrow = "▼"
                change_object_name = "rateDown"
            else:
                arrow = "•"
                change_object_name = "rateNeutral"

            change = QLabel(f"{arrow}  {rate.formatted_change()}")
            change.setObjectName(change_object_name)

            entry_layout.addWidget(symbol)
            entry_layout.addWidget(value)
            entry_layout.addWidget(change)
            layout.addWidget(entry)

        if self._cache_state in {"expired", "stale"}:
            stale = QLabel("Último dato disponible")
            stale.setObjectName("rateStale")
            layout.addWidget(stale)

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
            self._scroll_clock.start()
            self._scroll_timer.start()

    def _advance_ticker(self) -> None:
        elapsed_ms = self._FRAME_INTERVAL_MS
        if self._scroll_clock.isValid():
            elapsed_ms = max(self._scroll_clock.restart(), 1)

        self._advance_ticker_by(elapsed_ms)

    def _advance_ticker_by(self, elapsed_ms: int) -> None:
        if self._track is None or self._cycle_width <= 0:
            return

        distance = self._SCROLL_SPEED_PX_PER_SECOND * elapsed_ms / 1000
        self._offset = (self._offset + distance) % self._cycle_width
        self._position_track()

    def _position_track(self) -> None:
        if self._track is None:
            return
        size_hint = self._track.sizeHint()
        track_height = max(size_hint.height(), self._viewport.height())
        self._track.resize(size_hint.width(), track_height)
        y = (self._viewport.height() - track_height) // 2
        self._track.move(-round(self._offset), y)
