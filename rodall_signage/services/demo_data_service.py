from __future__ import annotations
from rodall_signage.models import ReferenceItem, ReferenceSnapshot, WeatherSnapshot
from datetime import date, datetime, timedelta, timezone

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
            display_weather_code=2,
            description="Parcialmente nublado",
            wind_speed_kmh=18,
            observation_time=now.replace(tzinfo=None),
        )

    @staticmethod
    def references() -> ReferenceSnapshot:
        now = datetime.now(timezone.utc)
        values = (
            ("1", "REF-0821", "Grupo Industrial del Golfo", "I", "Importación", "Veracruz", "DESPACHADO"),
            ("2", "REF-0822", "Comercializadora del Centro", "E", "Exportación", "Manzanillo", "EN TRÁMITE"),
            ("3", "REF-0823", "Distribuidora Nacional", "I", "Importación", "Veracruz", "PEND. DOCS"),
        )
        return ReferenceSnapshot(
            fetched_at_utc=now,
            references=tuple(
                ReferenceItem(
                    id=item_id,
                    reference_number=number,
                    reference_date=date.today(),
                    client=client,
                    operation_code=operation_code,
                    operation=operation,
                    document="A1",
                    customs_office_number=430,
                    customs_office=customs_office,
                    status_code="A",
                    status=status,
                    last_external_update_at=now,
                )
                for (
                    item_id,
                    number,
                    client,
                    operation_code,
                    operation,
                    customs_office,
                    status,
                ) in values
            ),
        )
