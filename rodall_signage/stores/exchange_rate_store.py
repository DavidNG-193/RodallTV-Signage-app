from __future__ import annotations

from datetime import datetime
import math
from pathlib import Path

from rodall_signage.cache.cache_models import CacheReadResult
from rodall_signage.cache.json_cache_store import JsonCacheStore
from rodall_signage.models import ExchangeRate, RateTrend


class ExchangeRateStore:
    SCHEMA_VERSION = 1

    def __init__(self, path: Path) -> None:
        self._cache = JsonCacheStore[list[ExchangeRate]](
            path=path,
            schema_version=self.SCHEMA_VERSION,
            serialize_payload=self._serialize,
            parse_payload=self._parse,
        )

    @property
    def path(self) -> Path:
        return self._cache.path

    def read(self) -> CacheReadResult[list[ExchangeRate]]:
        return self._cache.read()

    def write(
        self,
        rates: list[ExchangeRate],
        generated_at: datetime,
        expires_at: datetime | None,
    ) -> None:
        self._cache.write_atomic(list(rates), generated_at, expires_at)

    def delete(self) -> None:
        self._cache.delete()

    @staticmethod
    def _serialize(rates: list[ExchangeRate]) -> object:
        return [
            {
                "currency": rate.currency,
                "label": rate.label,
                "value": rate.value,
                "trend": rate.trend.value,
                "changePercent": rate.change_percent,
            }
            for rate in rates
        ]

    @staticmethod
    def _parse(payload: object) -> list[ExchangeRate]:
        if not isinstance(payload, list):
            raise TypeError("El payload de tasas debe ser una lista.")

        rates: list[ExchangeRate] = []
        for raw in payload:
            if not isinstance(raw, dict):
                raise TypeError("Cada tasa debe ser un objeto.")

            currency = ExchangeRateStore._required_text(raw, "currency")
            label = ExchangeRateStore._required_text(raw, "label")
            value = ExchangeRateStore._finite_number(raw.get("value"), "value")
            change = raw.get("changePercent")
            rates.append(
                ExchangeRate(
                    currency=currency,
                    label=label,
                    value=value,
                    trend=RateTrend(str(raw["trend"])),
                    change_percent=(
                        ExchangeRateStore._finite_number(
                            change,
                            "changePercent",
                        )
                        if change is not None
                        else None
                    ),
                )
            )

        return rates

    @staticmethod
    def _required_text(raw: dict, key: str) -> str:
        value = raw[key]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} es obligatorio.")
        return value.strip()

    @staticmethod
    def _finite_number(value: object, field: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{field} debe ser numérico.")
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError(f"{field} debe ser finito.")
        return parsed
