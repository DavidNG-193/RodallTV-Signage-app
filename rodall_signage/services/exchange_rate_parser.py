from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from rodall_signage.models.exchange_rate import (
    ExchangeRate,
    ExchangeRateSnapshot,
)


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError("La fecha UTC debe ser texto.")

    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def parse_exchange_rate_snapshot(
    payload: dict[str, Any],
) -> ExchangeRateSnapshot:
    enabled = payload.get("enabled", False)
    if type(enabled) is not bool:
        raise ValueError("enabled debe ser booleano.")
    source = str(payload.get("source", "")).strip()
    is_stale = payload.get("isStale", False)
    if type(is_stale) is not bool:
        raise ValueError("isStale debe ser booleano.")

    raw_rates = payload.get("rates", [])

    if not isinstance(raw_rates, list):
        raise ValueError("rates debe ser una lista.")

    parsed_rates: list[ExchangeRate] = []

    for raw in raw_rates:
        if not isinstance(raw, dict):
            raise ValueError("Cada tasa debe ser un objeto.")

        try:
            numeric_value = Decimal(str(raw["value"]))
            effective_date = date.fromisoformat(
                str(raw["effectiveDate"])
            )
            position = int(raw["position"])
            series_id = str(raw["seriesId"]).strip()
            display_name = str(raw["displayName"]).strip()
            unit = str(raw["unit"]).strip()
            raw_change = raw.get("changePercent")
            change_percent = (
                Decimal(str(raw_change)) if raw_change is not None else None
            )
        except (KeyError, InvalidOperation, ValueError) as exc:
            raise ValueError("La tasa contiene datos inválidos.") from exc

        if (
            not numeric_value.is_finite()
            or position <= 0
            or not series_id
            or not display_name
            or not unit
            or (
                change_percent is not None
                and not change_percent.is_finite()
            )
        ):
            raise ValueError("La tasa contiene datos inválidos.")

        parsed_rates.append(
            ExchangeRate(
                series_id=series_id,
                display_name=display_name,
                value=numeric_value,
                unit=unit,
                effective_date=effective_date,
                change_percent=change_percent,
                position=position,
            )
        )

    parsed_rates.sort(key=lambda item: item.position)

    return ExchangeRateSnapshot(
        enabled=enabled,
        fetched_at_utc=_parse_datetime(payload.get("fetchedAtUtc")),
        expires_at_utc=_parse_datetime(payload.get("expiresAtUtc")),
        source=source,
        is_stale=is_stale,
        rates=tuple(parsed_rates),
    )
