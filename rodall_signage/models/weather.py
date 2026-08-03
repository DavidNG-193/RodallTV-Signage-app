from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class WeatherSnapshot:
    location: str
    temperature_celsius: float | None
    condition: str
    humidity_percent: int | None = None
    wind_kph: float | None = None

    def temperature_text(self) -> str:
        if self.temperature_celsius is None:
            return "--°C"
        return f"{round(self.temperature_celsius)}°C"

    def details_text(self) -> str:
        details: list[str] = []
        if self.humidity_percent is not None:
            details.append(f"Humedad: {self.humidity_percent}%")
        if self.wind_kph is not None:
            details.append(f"Viento: {self.wind_kph:.0f} km/h")
        return "  •  ".join(details)