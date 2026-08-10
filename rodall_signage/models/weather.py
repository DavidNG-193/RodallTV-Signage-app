from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class WeatherSnapshot:
    enabled: bool
    location_name: str | None
    fetched_at_utc: datetime | None
    expires_at_utc: datetime | None
    is_stale: bool
    temperature_c: float | None
    apparent_temperature_c: float | None
    relative_humidity_percent: int | None
    precipitation_mm: float | None
    weather_code: int | None
    description: str | None
    wind_speed_kmh: float | None
    observation_time: datetime | None

    def temperature_text(self) -> str:
        if self.temperature_c is None:
            return "--°C"
        return f"{round(self.temperature_c)}°C"

    def apparent_temperature_text(self) -> str:
        if self.apparent_temperature_c is None:
            return "Sensación: --"
        return f"Sensación: {round(self.apparent_temperature_c)}°C"
