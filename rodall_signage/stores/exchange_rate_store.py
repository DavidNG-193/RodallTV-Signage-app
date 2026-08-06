from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from rodall_signage.cache.cache_models import CacheReadResult
from rodall_signage.cache.json_cache_store import JsonCacheStore
from rodall_signage.models import ExchangeRate, ExchangeRateSnapshot


class ExchangeRateStore:
    SCHEMA_VERSION = 2

    def __init__(self, path: Path) -> None:
        self._cache = JsonCacheStore[ExchangeRateSnapshot](
            path=path,
            schema_version=self.SCHEMA_VERSION,
            serialize_payload=self._serialize,
            parse_payload=self._parse,
        )

    @property
    def path(self) -> Path:
        return self._cache.path

    def read(self) -> CacheReadResult[ExchangeRateSnapshot]:
        return self._cache.read()

    def save(self, snapshot: ExchangeRateSnapshot) -> None:
        generated_at = snapshot.fetched_at_utc or datetime.now(timezone.utc)
        self._cache.write_atomic(
            snapshot,
            generated_at=generated_at,
            expires_at=snapshot.expires_at_utc,
        )

    def delete(self) -> None:
        self._cache.delete()

    @staticmethod
    def _serialize(snapshot: ExchangeRateSnapshot) -> object:
        return {
            "enabled": snapshot.enabled,
            "fetchedAtUtc": ExchangeRateStore._format_datetime(
                snapshot.fetched_at_utc
            ),
            "expiresAtUtc": ExchangeRateStore._format_datetime(
                snapshot.expires_at_utc
            ),
            "source": snapshot.source,
            "isStale": snapshot.is_stale,
            "rates": [
                {
                    "seriesId": rate.series_id,
                    "displayName": rate.display_name,
                    "value": str(rate.value),
                    "unit": rate.unit,
                    "effectiveDate": rate.effective_date.isoformat(),
                    "changePercent": (
                        str(rate.change_percent)
                        if rate.change_percent is not None
                        else None
                    ),
                    "position": rate.position,
                }
                for rate in snapshot.rates
            ],
        }

    @staticmethod
    def _parse(payload: object) -> ExchangeRateSnapshot:
        if not isinstance(payload, dict):
            raise TypeError("El payload de tasas debe ser un objeto.")

        enabled = ExchangeRateStore._required_bool(payload, "enabled")
        is_stale = ExchangeRateStore._required_bool(payload, "isStale")
        raw_rates = payload.get("rates")
        if not isinstance(raw_rates, list):
            raise TypeError("rates debe ser una lista.")

        rates: list[ExchangeRate] = []
        for raw in raw_rates:
            if not isinstance(raw, dict):
                raise TypeError("Cada tasa debe ser un objeto.")

            try:
                value = Decimal(str(raw["value"]))
                effective_date = date.fromisoformat(str(raw["effectiveDate"]))
                position = int(raw["position"])
                raw_change = raw.get("changePercent")
                change_percent = (
                    Decimal(str(raw_change))
                    if raw_change is not None
                    else None
                )
            except (KeyError, InvalidOperation, ValueError) as error:
                raise ValueError("La tasa contiene datos inválidos.") from error

            if (
                not value.is_finite()
                or position <= 0
                or (
                    change_percent is not None
                    and not change_percent.is_finite()
                )
            ):
                raise ValueError("El valor o la posición de la tasa es inválido.")

            rates.append(
                ExchangeRate(
                    series_id=ExchangeRateStore._required_text(raw, "seriesId"),
                    display_name=ExchangeRateStore._required_text(
                        raw, "displayName"
                    ),
                    value=value,
                    unit=ExchangeRateStore._required_text(raw, "unit"),
                    effective_date=effective_date,
                    change_percent=change_percent,
                    position=position,
                )
            )

        rates.sort(key=lambda item: item.position)
        return ExchangeRateSnapshot(
            enabled=enabled,
            fetched_at_utc=ExchangeRateStore._parse_datetime(
                payload.get("fetchedAtUtc")
            ),
            expires_at_utc=ExchangeRateStore._parse_datetime(
                payload.get("expiresAtUtc")
            ),
            source=str(payload.get("source", "")).strip(),
            is_stale=is_stale,
            rates=tuple(rates),
        )

    @staticmethod
    def _required_text(raw: dict, key: str) -> str:
        value = raw[key]
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
    def _parse_datetime(value: object) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise TypeError("La fecha UTC debe ser texto.")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _format_datetime(value: datetime | None) -> str | None:
        if value is None:
            return None
        normalized = (
            value.replace(tzinfo=timezone.utc)
            if value.tzinfo is None
            else value.astimezone(timezone.utc)
        )
        return normalized.isoformat().replace("+00:00", "Z")
