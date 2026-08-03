from __future__ import annotations
from rodall_signage.models import DailyReference, ExchangeRate, RateTrend, WeatherSnapshot

class DemoDataService:
    @staticmethod
    def exchange_rates() -> list[ExchangeRate]:
        return [
            ExchangeRate("USD", "USD / MXN", 18.6241, RateTrend.UP, 0.12),
            ExchangeRate("EUR", "EUR / MXN", 21.4078, RateTrend.DOWN, -0.08),
            ExchangeRate("CAD", "CAD / MXN", 13.5427, RateTrend.NEUTRAL, 0.00),
            ExchangeRate("GBP", "GBP / MXN", 24.8913, RateTrend.UP, 0.21),
        ]

    @staticmethod
    def weather() -> WeatherSnapshot:
        return WeatherSnapshot(
            location="Veracruz, VER",
            temperature_celsius=29,
            condition="Parcialmente nublado",
            humidity_percent=76,
            wind_kph=18,
        )

    @staticmethod
    def references() -> list[DailyReference]:
        return [
            DailyReference(
                "1", "REF-0821", "Grupo Industrial del Golfo", 1,
                "Veracruz", "Importación", "DESPACHADO",
            ),
            DailyReference(
                "2", "REF-0822", "Comercializadora del Centro", 2,
                "Manzanillo", "Exportación", "EN TRÁMITE",
            ),
            DailyReference(
                "3", "REF-0823", "Distribuidora Nacional", 3,
                "Veracruz", "Importación", "PEND. DOCS",
            ),
            DailyReference(
                "4", "REF-0824", "Maquiladora Fronteriza", 4,
                "Nuevo Laredo", "Exportación", "DESPACHADO",
            ),
            DailyReference(
                "5", "REF-0825", "Importadora del Sureste", 5,
                "Veracruz", "Importación", "EN TRÁMITE",
            ),
            DailyReference(
                "6", "REF-0826", "Agroexportaciones MX", 6,
                "Manzanillo", "Exportación", "DESPACHADO",
            ),
        ]
