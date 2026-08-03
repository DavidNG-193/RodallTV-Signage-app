from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum

class RateTrend(StrEnum):
    UP = "Up"
    DOWN = "Down"
    NEUTRAL = "Neutral"

@dataclass(frozen=True, slots=True)
class ExchangeRate:
    currency: str
    label: str
    value: float
    trend: RateTrend = RateTrend.NEUTRAL
    change_percent: float | None = None

    def formatted_value(self) -> str:
        return f"{self.value:,.4f}"

    def formatted_change(self) -> str:
        if self.change_percent is None:
            return "0.00%"

        return f"{self.change_percent:+.2f}%"
