from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any

from rodall_signage.models.weather import WeatherSnapshot


def _utc_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Se esperaba fecha UTC en texto.")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _local_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Se esperaba fecha de observación en texto.")
    return datetime.fromisoformat(value)


def _finite_number(payload: dict[str, Any], key: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"El clima no contiene un {key} válido.")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"El clima no contiene un {key} finito.")
    return parsed


def parse_weather_snapshot(payload: dict[str, Any]) -> WeatherSnapshot:
    enabled = payload.get("enabled", False)
    if type(enabled) is not bool:
        raise ValueError("enabled debe ser booleano.")

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
            description=None,
            wind_speed_kmh=None,
            observation_time=None,
        )

    is_stale = payload.get("isStale", False)
    if type(is_stale) is not bool:
        raise ValueError("isStale debe ser booleano.")

    location_name = payload.get("locationName")
    description = payload.get("description")
    humidity = payload.get("relativeHumidityPercent")
    weather_code = payload.get("weatherCode")
    if not isinstance(location_name, str) or not location_name.strip():
        raise ValueError("El clima no contiene locationName.")
    if not isinstance(description, str) or not description.strip():
        raise ValueError("El clima no contiene description.")
    if type(humidity) is not int or not 0 <= humidity <= 100:
        raise ValueError("La humedad debe estar entre 0 y 100.")
    if type(weather_code) is not int or weather_code < 0:
        raise ValueError("weatherCode debe ser un entero no negativo.")

    precipitation = _finite_number(payload, "precipitationMm")
    wind = _finite_number(payload, "windSpeedKmh")
    if precipitation < 0 or wind < 0:
        raise ValueError("Precipitación y viento no pueden ser negativos.")

    return WeatherSnapshot(
        enabled=True,
        location_name=location_name.strip(),
        fetched_at_utc=_utc_datetime(payload.get("fetchedAtUtc")),
        expires_at_utc=_utc_datetime(payload.get("expiresAtUtc")),
        is_stale=is_stale,
        temperature_c=_finite_number(payload, "temperatureC"),
        apparent_temperature_c=_finite_number(
            payload,
            "apparentTemperatureC",
        ),
        relative_humidity_percent=humidity,
        precipitation_mm=precipitation,
        weather_code=weather_code,
        description=description.strip(),
        wind_speed_kmh=wind,
        observation_time=_local_datetime(payload.get("observationTime")),
    )
