from __future__ import annotations

from datetime import datetime
import math
from pathlib import Path

from rodall_signage.cache.cache_models import CacheReadResult
from rodall_signage.cache.json_cache_store import JsonCacheStore
from rodall_signage.models import WeatherSnapshot


class WeatherStore:
    SCHEMA_VERSION = 1

    def __init__(self, path: Path) -> None:
        self._cache = JsonCacheStore[WeatherSnapshot](
            path=path,
            schema_version=self.SCHEMA_VERSION,
            serialize_payload=self._serialize,
            parse_payload=self._parse,
        )

    @property
    def path(self) -> Path:
        return self._cache.path

    def read(self) -> CacheReadResult[WeatherSnapshot]:
        return self._cache.read()

    def write(
        self,
        weather: WeatherSnapshot,
        generated_at: datetime,
        expires_at: datetime | None,
    ) -> None:
        self._cache.write_atomic(weather, generated_at, expires_at)

    def delete(self) -> None:
        self._cache.delete()

    @staticmethod
    def _serialize(weather: WeatherSnapshot) -> object:
        return {
            "location": weather.location,
            "temperatureCelsius": weather.temperature_celsius,
            "condition": weather.condition,
            "humidityPercent": weather.humidity_percent,
            "windKph": weather.wind_kph,
        }

    @staticmethod
    def _parse(payload: object) -> WeatherSnapshot:
        if not isinstance(payload, dict):
            raise TypeError("El payload de clima debe ser un objeto.")

        location = WeatherStore._required_text(payload, "location")
        condition = WeatherStore._required_text(payload, "condition")
        temperature = WeatherStore._optional_number(
            payload.get("temperatureCelsius"),
            "temperatureCelsius",
        )
        wind = WeatherStore._optional_number(payload.get("windKph"), "windKph")
        humidity_raw = payload.get("humidityPercent")

        if humidity_raw is None:
            humidity = None
        elif type(humidity_raw) is not int or not 0 <= humidity_raw <= 100:
            raise ValueError("humidityPercent debe estar entre 0 y 100.")
        else:
            humidity = humidity_raw

        if wind is not None and wind < 0:
            raise ValueError("windKph no puede ser negativo.")

        return WeatherSnapshot(
            location=location,
            temperature_celsius=temperature,
            condition=condition,
            humidity_percent=humidity,
            wind_kph=wind,
        )

    @staticmethod
    def _required_text(raw: dict, key: str) -> str:
        value = raw[key]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} es obligatorio.")
        return value.strip()

    @staticmethod
    def _optional_number(value: object, field: str) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{field} debe ser numérico o null.")
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError(f"{field} debe ser finito.")
        return parsed
