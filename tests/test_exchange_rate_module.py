from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import os
import shutil
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

from rodall_signage.cache.cache_models import CacheFreshness
from rodall_signage.services.exchange_rate_parser import (
    parse_exchange_rate_snapshot,
)
from rodall_signage.stores.exchange_rate_store import ExchangeRateStore
from rodall_signage.ui.widgets import ExchangeRateBar


class ExchangeRateModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.root = Path(__file__).parents[1] / "runtime" / "cache" / "rate-tests"
        self.root.mkdir(parents=True, exist_ok=True)
        for path in self.root.iterdir():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

    def tearDown(self) -> None:
        for path in self.root.iterdir():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

    @staticmethod
    def _payload() -> dict:
        fetched_at = datetime.now(timezone.utc)
        return {
            "enabled": True,
            "fetchedAtUtc": fetched_at.isoformat().replace("+00:00", "Z"),
            "expiresAtUtc": "2026-08-05T22:00:00Z",
            "source": "Banco de México SIE",
            "isStale": False,
            "rates": [
                {
                    "seriesId": "SF46410",
                    "displayName": "EUR / MXN",
                    "value": 20.4102,
                    "unit": "MXN",
                    "effectiveDate": "2026-08-05",
                    "changePercent": -0.15,
                    "position": 2,
                },
                {
                    "seriesId": "SF43718",
                    "displayName": "USD / MXN",
                    "value": 18.7523,
                    "unit": "MXN",
                    "effectiveDate": "2026-08-05",
                    "changePercent": 0.12,
                    "position": 1,
                },
            ],
        }

    def test_parser_preserves_decimal_and_orders_by_position(self) -> None:
        snapshot = parse_exchange_rate_snapshot(self._payload())

        self.assertTrue(snapshot.enabled)
        self.assertEqual(snapshot.rates[0].series_id, "SF43718")
        self.assertEqual(snapshot.rates[0].value, Decimal("18.7523"))
        self.assertEqual(snapshot.rates[0].change_percent, Decimal("0.12"))
        self.assertEqual(snapshot.fetched_at_utc.tzinfo, timezone.utc)

    def test_store_roundtrip_uses_text_for_decimal(self) -> None:
        store = ExchangeRateStore(self.root / "exchange_rates.json")
        snapshot = parse_exchange_rate_snapshot(self._payload())
        store.save(snapshot)

        raw = json.loads(store.path.read_text(encoding="utf-8"))
        self.assertEqual(raw["schemaVersion"], 2)
        self.assertEqual(raw["payload"]["rates"][0]["value"], "18.7523")

        result = store.read()
        self.assertTrue(result.has_data)
        self.assertEqual(result.freshness, CacheFreshness.EXPIRED)
        self.assertEqual(result.envelope.payload.rates, snapshot.rates)

    def test_invalid_payload_does_not_replace_last_valid_cache(self) -> None:
        store = ExchangeRateStore(self.root / "exchange_rates.json")
        snapshot = parse_exchange_rate_snapshot(self._payload())
        store.save(snapshot)
        previous = store.path.read_bytes()

        invalid = self._payload()
        invalid["rates"][0]["value"] = "N/E"
        with self.assertRaises(ValueError):
            store.save(parse_exchange_rate_snapshot(invalid))

        self.assertEqual(store.path.read_bytes(), previous)

    def test_disabled_contract_is_valid_without_rates(self) -> None:
        snapshot = parse_exchange_rate_snapshot(
            {
                "enabled": False,
                "fetchedAtUtc": None,
                "expiresAtUtc": None,
                "source": "Banco de México SIE",
                "isStale": False,
                "rates": [],
            }
        )

        self.assertFalse(snapshot.enabled)
        self.assertEqual(snapshot.rates, ())

    def test_late_snapshot_reveals_replaced_ticker_track(self) -> None:
        widget = ExchangeRateBar()
        widget.resize(1280, 48)
        widget.show()
        self.app.processEvents()

        widget.set_snapshot(parse_exchange_rate_snapshot(self._payload()))
        self.app.processEvents()

        self.assertTrue(widget._track.isVisible())
        visible_text = [
            label.text()
            for label in widget._track.findChildren(QLabel)
            if label.isVisible()
        ]
        self.assertIn("USD / MXN", visible_text)
        self.assertIn("18.7523", visible_text)
        self.assertIn("▲  +0.12%", visible_text)
        update_lines = widget._effective_date.text().splitlines()
        self.assertRegex(
            update_lines[0],
            r"^Consultado: hoy \d{2}:\d{2}$",
        )
        self.assertEqual(update_lines[1], "BANXICO 05 AGO.")
        self.assertNotIn("05/08/2026", visible_text)

    def test_ticker_catches_up_after_a_delayed_frame(self) -> None:
        widget = ExchangeRateBar()
        widget._cycle_width = 500

        widget._advance_ticker_by(120)

        self.assertAlmostEqual(widget._offset, 5.0)


if __name__ == "__main__":
    unittest.main()
