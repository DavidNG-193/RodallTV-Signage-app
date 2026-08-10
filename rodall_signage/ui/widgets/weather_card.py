from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from rodall_signage.models import WeatherSnapshot


class WeatherCard(QFrame):
    _ICONS_DIR = Path(__file__).resolve().parents[3] / "icons"
    _PNG_ICONS = {
        0: "muySoleado.png",
        1: "desoejado.png",
        2: "parcialmenteNublado.png",
        3: "nublado.png",
        45: "neblina.png",
        48: "neblina.png",
        51: "llovizna.png",
        53: "llovizna.png",
        55: "llovizna.png",
        61: "lluvia.png",
        63: "lluvia.png",
        65: "lluvia.png",
        80: "lluvia.png",
        81: "lluvia.png",
        82: "lluvia.png",
        95: "tormenta.png",
        96: "tormenta.png",
        99: "tormenta.png",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("weatherCard")
        self.setFixedHeight(158)
        self._snapshot: WeatherSnapshot | None = None
        self._cache_state = "missing"
        self._icon_size = 50

        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(4)

        self._location = QLabel("Clima no disponible")
        self._location.setObjectName("weatherLocation")

        current_row = QHBoxLayout()
        current_row.setContentsMargins(0, 0, 0, 0)
        current_row.setSpacing(9)

        self._icon = QLabel("☁")
        self._icon.setObjectName("weatherIcon")
        self._icon.setAlignment(Qt.AlignCenter)
        self._icon.setFixedSize(self._icon_size, self._icon_size)

        self._temperature = QLabel("--°C")
        self._temperature.setObjectName("weatherValue")

        self._condition = QLabel("Sin información del clima")
        self._condition.setObjectName("weatherCondition")
        self._condition.setWordWrap(True)

        self._apparent = QLabel("Sensación: --")
        self._apparent.setObjectName("weatherApparent")

        condition_column = QVBoxLayout()
        condition_column.setContentsMargins(0, 0, 0, 0)
        condition_column.setSpacing(1)
        condition_column.addWidget(self._condition)
        condition_column.addWidget(self._apparent)

        current_row.addWidget(self._icon, 0)
        current_row.addWidget(self._temperature, 0)
        current_row.addSpacing(3)
        current_row.addLayout(condition_column, 1)

        divider = QFrame()
        divider.setObjectName("weatherDivider")
        divider.setFrameShape(QFrame.HLine)

        details_row = QHBoxLayout()
        details_row.setContentsMargins(0, 3, 0, 0)
        self._humidity = QLabel("Humedad: --")
        self._humidity.setObjectName("weatherDetail")
        self._wind = QLabel("Viento: --")
        self._wind.setObjectName("weatherDetailStrong")
        self._wind.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        details_row.addWidget(self._humidity, 1)
        details_row.addWidget(self._wind, 1)

        self._availability = QLabel("")
        self._availability.setObjectName("weatherAvailability")
        self._availability.setAlignment(Qt.AlignRight)

        self._layout.addWidget(self._location)
        self._layout.addLayout(current_row)
        self._layout.addWidget(divider)
        self._layout.addLayout(details_row)
        self._layout.addWidget(self._availability)

        self.show_empty_state()

    def set_snapshot(self, snapshot: WeatherSnapshot) -> None:
        self._snapshot = snapshot
        if not snapshot.enabled:
            self.show_empty_state()
            return

        self._location.setText(snapshot.location_name or "Sin ubicación")
        self._temperature.setText(snapshot.temperature_text())
        self._condition.setText(snapshot.description or "Sin información")
        self._apparent.setText(snapshot.apparent_temperature_text())
        self._humidity.setText(
            f"Humedad: {snapshot.relative_humidity_percent}%"
            if snapshot.relative_humidity_percent is not None
            else "Humedad: --"
        )
        self._wind.setText(
            f"Viento: {snapshot.wind_speed_kmh:.0f} km/h"
            if snapshot.wind_speed_kmh is not None
            else "Viento: --"
        )
        self._set_icon(snapshot.weather_code)
        self._update_availability()

    def set_weather(self, weather: WeatherSnapshot | None) -> None:
        """Alias temporal para consumidores del módulo de caché anterior."""
        if weather is None:
            self.show_empty_state()
        else:
            self.set_snapshot(weather)

    def set_cache_state(self, state: str) -> None:
        self._cache_state = state.strip().lower()
        if self._cache_state in {"missing", "invalid"}:
            if self._snapshot is None or not self._snapshot.enabled:
                self.show_empty_state()
                return
        self._update_availability()

    def show_empty_state(self) -> None:
        self._snapshot = None
        self._location.setText("Clima no disponible")
        self._temperature.setText("--°C")
        self._condition.setText("Sin información del clima")
        self._apparent.setText("Sensación: --")
        self._humidity.setText("Humedad: --")
        self._wind.setText("Viento: --")
        self._icon.clear()
        self._icon.setText("☁")
        self._availability.setText("")

    def set_content_margins(self, padding: int) -> None:
        compact_padding = max(padding - 4, 8)
        self._layout.setContentsMargins(
            compact_padding,
            compact_padding,
            compact_padding,
            compact_padding,
        )

        if padding >= 20:
            height, icon_size = 180, 56
        elif padding >= 16:
            height, icon_size = 158, 50
        else:
            height, icon_size = 142, 44

        self.setFixedHeight(height)
        self._icon_size = icon_size
        self._icon.setFixedSize(icon_size, icon_size)
        if self._snapshot is not None and self._snapshot.enabled:
            self._set_icon(self._snapshot.weather_code)

    def _update_availability(self) -> None:
        if self._snapshot is None or not self._snapshot.enabled:
            self._availability.setText("")
        elif self._snapshot.is_stale or self._cache_state == "stale":
            self._availability.setText("Último dato disponible")
        elif self._cache_state == "expired":
            self._availability.setText("Sin actualización reciente")
        else:
            self._availability.setText("")

    @staticmethod
    def _icon_for_code(code: int | None) -> str:
        if code == 0:
            return "☀"
        if code in {1, 2}:
            return "⛅"
        if code == 3:
            return "☁"
        if code in {45, 48}:
            return "🌫"
        if code in {*range(51, 68), *range(80, 83)}:
            return "🌧"
        if code in {*range(71, 78), 85, 86}:
            return "❄"
        if code in {95, 96, 99}:
            return "⛈"
        return "☁"

    def _set_icon(self, code: int | None) -> None:
        filename = self._PNG_ICONS.get(code)
        if filename is not None:
            pixmap = QPixmap(str(self._ICONS_DIR / filename))
            if not pixmap.isNull():
                self._icon.setText("")
                self._icon.setPixmap(
                    pixmap.scaled(
                        self._icon_size,
                        self._icon_size,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )
                return

        self._icon.clear()
        self._icon.setText(self._icon_for_code(code))
