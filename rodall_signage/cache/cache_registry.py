from __future__ import annotations

from dataclasses import dataclass

from rodall_signage.stores.exchange_rate_store import ExchangeRateStore
from rodall_signage.stores.reference_store import ReferenceStore
from rodall_signage.stores.weather_store import WeatherStore


@dataclass(slots=True)
class CacheRegistry:
    exchange_rates: ExchangeRateStore
    weather: WeatherStore
    references: ReferenceStore
