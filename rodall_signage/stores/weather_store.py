from __future__ import annotations

from datetime import datetime, timezone
import math
from pathlib import Path

from rodall_signage.cache.cache_models import CacheReadResult
from rodall_signage.cache.json_cache_store import JsonCacheStore
from rodall_signage.models import WeatherSnapshot


class WeatherStore:
    SCHEMA_VERSION = 2

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

    def save(self, snapshot: WeatherSnapshot) -> None:
        generated_at = snapshot.fetched_at_utc or datetime.now(timezone.utc)
        self._cache.write_atomic(
            snapshot,
            generated_at=generated_at,
            expires_at=snapshot.expires_at_utc,
        )

    def write(
        self,
        snapshot: WeatherSnapshot,
        generated_at: datetime,
        expires_at: datetime | None,
    ) -> None:
        """Compatibilidad con las utilidades de caché del módulo 06."""
        self._cache.write_atomic(snapshot, generated_at, expires_at)

    def delete(self) -> None:
        self._cache.delete()

    @staticmethod
    def _serialize(snapshot: WeatherSnapshot) -> object:
        return {
            "enabled": snapshot.enabled,
            "locationName": snapshot.location_name,
            "fetchedAtUtc": WeatherStore._format_utc(
                snapshot.fetched_at_utc
            ),
            "expiresAtUtc": WeatherStore._format_utc(
                snapshot.expires_at_utc
            ),
            "isStale": snapshot.is_stale,
            "temperatureC": snapshot.temperature_c,
            "apparentTemperatureC": snapshot.apparent_temperature_c,
            "relativeHumidityPercent": snapshot.relative_humidity_percent,
            "precipitationMm": snapshot.precipitation_mm,
            "weatherCode": snapshot.weather_code,
            "displayWeatherCode": snapshot.display_weather_code,
            "description": snapshot.description,
            "windSpeedKmh": snapshot.wind_speed_kmh,
            "observationTime": (
                snapshot.observation_time.isoformat()
                if snapshot.observation_time is not None
                else None
            ),
        }

    @staticmethod
    def _parse(payload: object) -> WeatherSnapshot:
        if not isinstance(payload, dict):
            raise TypeError("El payload de clima debe ser un objeto.")

        enabled = WeatherStore._required_bool(payload, "enabled")
        is_stale = WeatherStore._required_bool(payload, "isStale")
        if not enabled:
            return WeatherSnapshot(
                enabled=False,
                location_name=None,
                fetched_at_utc=None,
                expires_at_utc=None,
                is_stale=False,
                temperature_c=None,
                apparent_temperature_c=None,
                relative_humidity_percent=None,
                precipitation_mm=None,
                weather_code=None,
                display_weather_code=None,
                description=None,
                wind_speed_kmh=None,
                observation_time=None,
            )

        location_name = WeatherStore._required_text(
            payload,
            "locationName",
        )
        description = WeatherStore._required_text(payload, "description")
        temperature = WeatherStore._required_number(payload, "temperatureC")
        apparent = WeatherStore._required_number(
            payload,
            "apparentTemperatureC",
        )
        precipitation = WeatherStore._required_number(
            payload,
            "precipitationMm",
        )
        wind = WeatherStore._required_number(payload, "windSpeedKmh")
        humidity = payload.get("relativeHumidityPercent")
        weather_code = payload.get("weatherCode")
        display_weather_code = payload.get(
            "displayWeatherCode",
            weather_code,
        )

        if type(humidity) is not int or not 0 <= humidity <= 100:
            raise ValueError(
                "relativeHumidityPercent debe estar entre 0 y 100."
            )
        if type(weather_code) is not int or weather_code < 0:
            raise ValueError("weatherCode debe ser un entero no negativo.")
        if type(display_weather_code) is not int or display_weather_code < 0:
            raise ValueError(
                "displayWeatherCode debe ser un entero no negativo."
            )
        if precipitation < 0 or wind < 0:
            raise ValueError("Precipitación y viento no pueden ser negativos.")

        return WeatherSnapshot(
            enabled=True,
            location_name=location_name,
            fetched_at_utc=WeatherStore._parse_utc(payload.get("fetchedAtUtc")),
            expires_at_utc=WeatherStore._parse_utc(payload.get("expiresAtUtc")),
            is_stale=is_stale,
            temperature_c=temperature,
            apparent_temperature_c=apparent,
            relative_humidity_percent=humidity,
            precipitation_mm=precipitation,
            weather_code=weather_code,
            display_weather_code=display_weather_code,
            description=description,
            wind_speed_kmh=wind,
            observation_time=WeatherStore._parse_local(
                payload.get("observationTime")
            ),
        )

    @staticmethod
    def _required_text(raw: dict, key: str) -> str:
        value = raw.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} es obligatorio.")
        return value.strip()

    @staticmethod
    def _required_bool(raw: dict, key: str) -> bool:
        value = raw.get(key)
        if type(value) is not bool:
            raise TypeError(f"{key} debe ser booleano.")
        return value

    @staticmethod
    def _required_number(raw: dict, key: str) -> float:
        value = raw.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{key} debe ser numérico.")
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError(f"{key} debe ser finito.")
        return parsed

    @staticmethod
    def _parse_utc(value: object) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise TypeError("La fecha UTC debe ser texto.")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _parse_local(value: object) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise TypeError("La fecha de observación debe ser texto.")
        return datetime.fromisoformat(value)

    @staticmethod
    def _format_utc(value: datetime | None) -> str | None:
        if value is None:
            return None
        normalized = (
            value.replace(tzinfo=timezone.utc)
            if value.tzinfo is None
            else value.astimezone(timezone.utc)
        )
        return normalized.isoformat().replace("+00:00", "Z")
