from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import shutil
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from rodall_signage.cache.cache_models import CacheFreshness
from rodall_signage.services.weather_parser import parse_weather_snapshot
from rodall_signage.services.weather_update_service import WeatherUpdateService
from rodall_signage.stores.weather_store import WeatherStore
from rodall_signage.ui.widgets import WeatherCard


def weather_payload(*, stale: bool = False) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "enabled": True,
        "locationName": "Veracruz, Veracruz",
        "fetchedAtUtc": now.isoformat().replace("+00:00", "Z"),
        "expiresAtUtc": (now + timedelta(minutes=15))
        .isoformat()
        .replace("+00:00", "Z"),
        "isStale": stale,
        "temperatureC": 29.3,
        "apparentTemperatureC": 34.1,
        "relativeHumidityPercent": 78,
        "precipitationMm": 0,
        "weatherCode": 2,
        "displayWeatherCode": 2,
        "description": "Parcialmente nublado",
        "windSpeedKmh": 13.2,
        "observationTime": "2026-08-07T09:15",
    }


class _FakeWeatherApi:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls = 0

    def get_weather(self) -> dict:
        self.calls += 1
        return self.payload


class WeatherModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.root = (
            Path(__file__).parents[1]
            / "runtime"
            / "cache"
            / "weather-tests"
        )
        self.root.mkdir(parents=True, exist_ok=True)
        self._clear()
        self.store = WeatherStore(self.root / "weather.json")

    def tearDown(self) -> None:
        self._clear()

    def _clear(self) -> None:
        for path in self.root.iterdir():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

    def test_parser_store_and_widget_preserve_complete_weather(self) -> None:
        snapshot = parse_weather_snapshot(weather_payload())
        self.store.save(snapshot)
        cached = self.store.read()

        self.assertEqual(cached.freshness, CacheFreshness.FRESH)
        self.assertEqual(cached.envelope.payload, snapshot)

        widget = WeatherCard()
        widget.set_snapshot(cached.envelope.payload)
        widget.set_cache_state("fresh")
        self.assertEqual(widget._location.text(), "Veracruz, Veracruz")
        self.assertEqual(widget._temperature.text(), "29°C")
        self.assertEqual(widget._apparent.text(), "Sensación: 34°C")
        self.assertEqual(widget._availability.text(), "")
        self.assertFalse(widget._icon.pixmap().isNull())

    def test_weather_icons_without_png_keep_the_existing_symbol(self) -> None:
        snapshot = parse_weather_snapshot(
            {
                **weather_payload(),
                "weatherCode": 71,
                "displayWeatherCode": 71,
                "description": "Nieve",
            }
        )
        widget = WeatherCard()
        widget.set_snapshot(snapshot)

        self.assertEqual(widget._icon.text(), "❄")
        self.assertTrue(widget._icon.pixmap().isNull())

    def test_widget_uses_display_code_and_preserves_provider_code(self) -> None:
        snapshot = parse_weather_snapshot(
            {
                **weather_payload(),
                "weatherCode": 95,
                "displayWeatherCode": 2,
                "description": "Posible tormenta",
            }
        )
        widget = WeatherCard()
        widget.set_snapshot(snapshot)

        self.assertEqual(snapshot.weather_code, 95)
        self.assertEqual(widget._condition.text(), "Posible tormenta")
        self.assertFalse(widget._icon.pixmap().isNull())

    def test_widget_can_present_uncertain_drizzle_as_cloudiness(self) -> None:
        snapshot = parse_weather_snapshot(
            {
                **weather_payload(),
                "weatherCode": 51,
                "displayWeatherCode": 2,
                "description": "Posible llovizna",
            }
        )
        widget = WeatherCard()
        widget.set_snapshot(snapshot)

        self.assertEqual(snapshot.weather_code, 51)
        self.assertEqual(snapshot.display_weather_code, 2)
        self.assertEqual(widget._condition.text(), "Posible llovizna")
        self.assertFalse(widget._icon.pixmap().isNull())

    def test_parser_keeps_compatibility_with_previous_responses(self) -> None:
        payload = weather_payload()
        payload.pop("displayWeatherCode")

        snapshot = parse_weather_snapshot(payload)

        self.assertEqual(snapshot.display_weather_code, snapshot.weather_code)

    def test_disabled_weather_is_a_valid_empty_state(self) -> None:
        snapshot = parse_weather_snapshot({"enabled": False})
        self.store.save(snapshot)
        widget = WeatherCard()
        widget.set_snapshot(snapshot)

        self.assertFalse(snapshot.enabled)
        self.assertEqual(widget._location.text(), "Clima no disponible")

    def test_expired_cache_remains_visible(self) -> None:
        snapshot = parse_weather_snapshot(weather_payload())
        expired = replace(
            snapshot,
            expires_at_utc=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        self.store.save(expired)
        result = self.store.read()
        widget = WeatherCard()
        widget.set_snapshot(result.envelope.payload)
        widget.set_cache_state(result.freshness.value)

        self.assertEqual(result.freshness, CacheFreshness.EXPIRED)
        self.assertEqual(widget._temperature.text(), "29°C")
        self.assertEqual(
            widget._availability.text(),
            "Sin actualización reciente",
        )

    def test_update_service_fetches_and_saves(self) -> None:
        api = _FakeWeatherApi(weather_payload())
        service = WeatherUpdateService(api, self.store, refresh_seconds=300)
        received = []
        loop = QEventLoop()

        def on_snapshot(snapshot: object) -> None:
            received.append(snapshot)
            loop.quit()

        service.snapshot_changed.connect(on_snapshot)
        QTimer.singleShot(3000, loop.quit)
        service.start()
        loop.exec()
        service.stop()

        self.assertEqual(api.calls, 1)
        self.assertEqual(len(received), 1)
        self.assertTrue(self.store.read().has_data)


if __name__ == "__main__":
    unittest.main()
