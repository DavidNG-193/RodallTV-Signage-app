from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ExchangeRate:
    series_id: str
    display_name: str
    value: Decimal
    unit: str
    effective_date: date
    change_percent: Decimal | None
    position: int

    def formatted_value(self) -> str:
        return f"{self.value:,.4f}"

    def formatted_change(self) -> str:
        if self.change_percent is None:
            return "—"
        return f"{self.change_percent:+.2f}%"


@dataclass(frozen=True, slots=True)
class ExchangeRateSnapshot:
    enabled: bool
    fetched_at_utc: datetime | None
    expires_at_utc: datetime | None
    source: str
    is_stale: bool
    rates: tuple[ExchangeRate, ...]
