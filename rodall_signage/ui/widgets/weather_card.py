from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from rodall_signage.models import WeatherSnapshot


class WeatherCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("weatherCard")
        self.setMinimumHeight(190)

        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(5)

        self._location = QLabel("Sin ubicación")
        self._location.setObjectName("weatherLocation")

        current_row = QHBoxLayout()
        current_row.setContentsMargins(0, 0, 0, 0)
        current_row.setSpacing(12)

        self._icon = QLabel("☀")
        self._icon.setObjectName("weatherIcon")
        self._icon.setAlignment(Qt.AlignCenter)

        self._temperature = QLabel("--°C")
        self._temperature.setObjectName("weatherValue")

        current_row.addWidget(self._icon, 0)
        current_row.addWidget(self._temperature, 1)

        self._condition = QLabel("Sin información del clima")
        self._condition.setObjectName("weatherCondition")
        self._condition.setWordWrap(True)

        divider = QFrame()
        divider.setObjectName("weatherDivider")
        divider.setFrameShape(QFrame.HLine)

        details_row = QHBoxLayout()
        details_row.setContentsMargins(0, 4, 0, 0)

        self._humidity = QLabel("Humedad: --")
        self._humidity.setObjectName("weatherDetail")
        self._wind = QLabel("Viento: --")
        self._wind.setObjectName("weatherDetailStrong")
        self._wind.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        details_row.addWidget(self._humidity, 1)
        details_row.addWidget(self._wind, 1)

        self._layout.addWidget(self._location)
        self._layout.addLayout(current_row)
        self._layout.addWidget(self._condition)
        self._layout.addWidget(divider)
        self._layout.addLayout(details_row)

    def set_weather(self, weather: WeatherSnapshot | None) -> None:
        if weather is None:
            self._location.setText("Sin ubicación")
            self._temperature.setText("--°C")
            self._condition.setText("Sin información del clima")
            self._humidity.setText("Humedad: --")
            self._wind.setText("Viento: --")
            self._icon.setText("☁")
            return

        self._location.setText(weather.location)
        self._temperature.setText(weather.temperature_text())
        self._condition.setText(weather.condition)
        self._humidity.setText(
            f"Humedad: {weather.humidity_percent}%"
            if weather.humidity_percent is not None
            else "Humedad: --"
        )
        self._wind.setText(
            f"Viento: {weather.wind_kph:.0f} km/h"
            if weather.wind_kph is not None
            else "Viento: --"
        )
        self._icon.setText(
            "☀" if "nublado" not in weather.condition.casefold() else "⛅"
        )

    def set_content_margins(self, padding: int) -> None:
        self._layout.setContentsMargins(padding, padding, padding, padding)

