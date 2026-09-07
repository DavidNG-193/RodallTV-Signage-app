from __future__ import annotations

from datetime import datetime, timedelta, timezone
from datetime import date
from decimal import Decimal
import json
import os
from pathlib import Path
import shutil
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from rodall_signage.cache.cache_models import CacheFreshness
from rodall_signage.cache.cache_registry import CacheRegistry
from rodall_signage.cache.json_cache_store import JsonCacheStore
from rodall_signage.services.cache_demo_service import CacheDemoService
from rodall_signage.models import (
    ExchangeRate,
    ExchangeRateSnapshot,
    WeatherSnapshot,
)
from rodall_signage.stores.exchange_rate_store import ExchangeRateStore
from rodall_signage.stores.reference_store import ReferenceStore
from rodall_signage.stores.weather_store import WeatherStore
from rodall_signage.ui.widgets import (
    ExchangeRateBar,
    ReferencesPanel,
    WeatherCard,
)


class CacheModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.root = (
            Path(__file__).parents[1]
            / "runtime"
            / "cache"
            / "cache-tests"
        )
        self.root.mkdir(parents=True, exist_ok=True)
        self._clear_directory(self.root)
        self.registry = CacheRegistry(
            exchange_rates=ExchangeRateStore(
                self.root / "exchange_rates.json"
            ),
            weather=WeatherStore(self.root / "weather.json"),
            references=ReferenceStore(self.root / "references.json"),
        )
        self.demo = CacheDemoService(self.registry)

    def _save_rates(
        self,
        *,
        expires_at: datetime | None = None,
    ) -> ExchangeRateSnapshot:
        now = datetime.now(timezone.utc)
        snapshot = ExchangeRateSnapshot(
            enabled=True,
            fetched_at_utc=now,
            expires_at_utc=expires_at or now + timedelta(hours=1),
            source="Banco de México SIE",
            is_stale=False,
            rates=(
                ExchangeRate(
                    series_id="SF43718",
                    display_name="USD / MXN",
                    value=Decimal("18.7523"),
                    unit="MXN",
                    effective_date=date(2026, 8, 5),
                    change_percent=Decimal("0.12"),
                    position=1,
                ),
            ),
        )
        self.registry.exchange_rates.save(snapshot)
        return snapshot

    def _save_weather(self) -> WeatherSnapshot:
        now = datetime.now(timezone.utc)
        snapshot = WeatherSnapshot(
            enabled=True,
            location_name="Veracruz, VER",
            fetched_at_utc=now,
            expires_at_utc=now + timedelta(minutes=15),
            is_stale=False,
            temperature_c=29.2,
            apparent_temperature_c=32.1,
            relative_humidity_percent=76,
            precipitation_mm=0,
            weather_code=2,
            display_weather_code=2,
            description="Parcialmente nublado",
            wind_speed_kmh=18,
            observation_time=datetime(2026, 8, 7, 9, 0),
        )
        self.registry.weather.save(snapshot)
        return snapshot

    def tearDown(self) -> None:
        self._clear_directory(self.root)

    @staticmethod
    def _clear_directory(root: Path) -> None:
        for path in root.iterdir():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

    def test_fresh_roundtrip_uses_utc_and_leaves_no_temporaries(self) -> None:
        self.demo.seed()
        self._save_rates()
        self._save_weather()

        results = (
            self.registry.exchange_rates.read(),
            self.registry.weather.read(),
            self.registry.references.read(),
        )
        self.assertTrue(all(result.has_data for result in results))
        self.assertTrue(
            all(result.freshness == CacheFreshness.FRESH for result in results)
        )
        self.assertEqual(len(results[0].envelope.payload.rates), 1)
        self.assertEqual(
            results[1].envelope.payload.location_name,
            "Veracruz, VER",
        )
        self.assertEqual(len(results[2].envelope.payload.references), 3)

        for path in (
            self.registry.exchange_rates.path,
            self.registry.weather.path,
            self.registry.references.path,
        ):
            raw = json.loads(path.read_text(encoding="utf-8"))
            expected_schema = 2
            self.assertEqual(raw["schemaVersion"], expected_schema)
            self.assertTrue(raw["generatedAt"].endswith("Z"))
            self.assertTrue(raw["expiresAt"].endswith("Z"))
            self.assertIn("payload", raw)
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_expired_cache_keeps_its_last_valid_payload(self) -> None:
        self.demo.seed()
        self._save_rates()
        self._save_weather()
        path = self.registry.references.path
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["generatedAt"] = (
            datetime.now(timezone.utc) - timedelta(days=2)
        ).isoformat().replace("+00:00", "Z")
        raw["expiresAt"] = (
            datetime.now(timezone.utc) - timedelta(days=1)
        ).isoformat().replace("+00:00", "Z")
        path.write_text(json.dumps(raw), encoding="utf-8")

        result = self.registry.references.read()

        self.assertEqual(result.freshness, CacheFreshness.EXPIRED)
        self.assertTrue(result.has_data)
        self.assertEqual(len(result.envelope.payload.references), 3)
        self.assertTrue(self.registry.references.path.exists())
        widget = ReferencesPanel()
        widget.set_snapshot(result.envelope.payload)
        self.assertEqual(len(widget._references), 3)

    def test_missing_cache_is_independent_from_other_stores(self) -> None:
        self.demo.seed()
        self._save_rates()
        self._save_weather()
        self.registry.references.delete()

        missing = self.registry.references.read()
        self.assertEqual(missing.freshness, CacheFreshness.MISSING)
        self.assertEqual(
            self.registry.exchange_rates.read().freshness,
            CacheFreshness.FRESH,
        )
        self.assertEqual(
            self.registry.weather.read().freshness,
            CacheFreshness.FRESH,
        )
        widget = ReferencesPanel()
        widget.set_references(
            missing.envelope.payload if missing.envelope is not None else []
        )
        self.assertEqual(widget._references, [])

    def test_corrupt_json_is_invalid_and_does_not_raise(self) -> None:
        self.demo.seed()
        self._save_rates()
        self._save_weather()
        self.registry.weather.path.write_text("{broken", encoding="utf-8")

        result = self.registry.weather.read()

        self.assertEqual(result.freshness, CacheFreshness.INVALID)
        self.assertFalse(result.has_data)
        self.assertTrue(result.message)
        self.assertEqual(
            self.registry.exchange_rates.read().freshness,
            CacheFreshness.FRESH,
        )
        widget = WeatherCard()
        widget.set_weather(
            result.envelope.payload if result.envelope is not None else None
        )
        self.assertEqual(widget._location.text(), "Clima no disponible")

    def test_incompatible_schema_is_invalid_and_file_is_preserved(self) -> None:
        self.demo.seed()
        self._save_rates()
        self._save_weather()
        path = self.registry.exchange_rates.path
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["schemaVersion"] = 999
        path.write_text(json.dumps(raw), encoding="utf-8")

        result = self.registry.exchange_rates.read()

        self.assertEqual(result.freshness, CacheFreshness.INVALID)
        self.assertFalse(result.has_data)
        self.assertIn("Esperada=2", result.message)
        self.assertTrue(path.exists())

    def test_failed_temporary_validation_preserves_active_cache(self) -> None:
        state = {"reject": False}

        def parse(payload: object) -> dict:
            if state["reject"]:
                raise ValueError("Fallo de validación forzado.")
            if not isinstance(payload, dict):
                raise TypeError("El payload debe ser un objeto.")
            return payload

        path = self.root / "atomic.json"
        store = JsonCacheStore[dict](path, 1, lambda payload: payload, parse)
        now = datetime.now(timezone.utc)
        store.write_atomic({"value": "anterior"}, now, None)
        active_before = path.read_bytes()
        state["reject"] = True

        with self.assertRaisesRegex(ValueError, "forzado"):
            store.write_atomic({"value": "nuevo"}, now, None)

        self.assertEqual(path.read_bytes(), active_before)
        self.assertFalse(path.with_suffix(".json.tmp").exists())
        state["reject"] = False
        self.assertEqual(store.read().envelope.payload["value"], "anterior")

    def test_widgets_receive_models_from_cache_results(self) -> None:
        self.demo.seed()
        self._save_rates()
        self._save_weather()
        rates = self.registry.exchange_rates.read()
        weather = self.registry.weather.read()
        references = self.registry.references.read()
        rate_widget = ExchangeRateBar()
        weather_widget = WeatherCard()
        reference_widget = ReferencesPanel()

        rate_widget.set_snapshot(rates.envelope.payload)
        weather_widget.set_weather(weather.envelope.payload)
        reference_widget.set_snapshot(references.envelope.payload)

        self.assertEqual(len(rate_widget._rates), 1)
        self.assertEqual(weather_widget._location.text(), "Veracruz, VER")
        self.assertEqual(len(reference_widget._references), 3)


if __name__ == "__main__":
    unittest.main()
