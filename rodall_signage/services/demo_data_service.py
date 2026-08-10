from __future__ import annotations
from rodall_signage.models import DailyReference, WeatherSnapshot
from datetime import datetime, timedelta, timezone

class DemoDataService:
    @staticmethod
    def weather() -> WeatherSnapshot:
        now = datetime.now(timezone.utc)
        return WeatherSnapshot(
            enabled=True,
            location_name="Veracruz, VER",
            fetched_at_utc=now,
            expires_at_utc=now + timedelta(minutes=15),
            is_stale=False,
            temperature_c=29,
            apparent_temperature_c=32,
            relative_humidity_percent=76,
            precipitation_mm=0,
            weather_code=2,
            description="Parcialmente nublado",
            wind_speed_kmh=18,
            observation_time=now.replace(tzinfo=None),
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
