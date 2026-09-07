from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from rodall_signage.cache.cache_models import CacheFreshness
from rodall_signage.services.reference_parser import parse_reference_snapshot
from rodall_signage.services.reference_update_service import (
    ReferenceUpdateService,
)
from rodall_signage.stores.reference_store import ReferenceStore
from rodall_signage.ui.widgets.references_panel import ReferencesPanel


def payload(references: list[dict] | None = None) -> dict:
    fetched_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "fetchedAtUtc": fetched_at,
        "references": references if references is not None else [
            {
                "id": "3c879dd2-fad1-4077-8654-76f33c30f511",
                "referenceNumber": "VER26-01234",
                "referenceDate": "2026-08-12",
                "client": "CLIENTE DE PRUEBA",
                "operationCode": "I",
                "operation": "Importación",
                "document": "A1",
                "customsOfficeNumber": 430,
                "customsOffice": "VERACRUZ",
                "statusCode": "A",
                "status": "ESTADO ACTUAL",
                "lastExternalUpdateAt": "2026-08-12T16:58:00Z",
            }
        ],
    }


class FakeApiClient:
    def get_references(self) -> dict:
        return payload()


class ReferenceModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.root = Path(__file__).parents[1] / "runtime" / "cache" / "reference-tests"
        self.root.mkdir(parents=True, exist_ok=True)
        for entry in self.root.iterdir():
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
        self.store = ReferenceStore(self.root / "references.json")

    def tearDown(self) -> None:
        for entry in self.root.iterdir():
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()

    def test_parser_store_and_panel_receive_models(self) -> None:
        snapshot = parse_reference_snapshot(payload())
        self.store.save(snapshot)
        cached = self.store.read()
        panel = ReferencesPanel()
        panel.set_snapshot(cached.envelope.payload)

        self.assertEqual(cached.freshness, CacheFreshness.FRESH)
        self.assertEqual(len(cached.envelope.payload.references), 1)
        self.assertEqual(panel._references[0].reference_number, "VER26-01234")

    def test_valid_empty_response_replaces_previous_cache_and_panel(self) -> None:
        self.store.save(parse_reference_snapshot(payload()))
        empty = parse_reference_snapshot(payload([]))
        self.store.save(empty)
        cached = self.store.read()
        panel = ReferencesPanel()
        panel.set_snapshot(cached.envelope.payload)

        self.assertEqual(cached.freshness, CacheFreshness.FRESH)
        self.assertEqual(cached.envelope.payload.references, ())
        self.assertEqual(panel._references, [])
        self.assertEqual(panel._empty_label.text(), "No hay referencias activas.")

    def test_invalid_payload_does_not_replace_valid_cache(self) -> None:
        initial = parse_reference_snapshot(payload())
        self.store.save(initial)
        before = self.store.path.read_bytes()
        service = ReferenceUpdateService(FakeApiClient(), self.store, 60)
        service._running = True
        service._on_success({"fetchedAtUtc": "bad", "references": []})

        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual(len(self.store.read().envelope.payload.references), 1)

    def test_corrupt_cache_is_invalid_without_crash(self) -> None:
        self.store.path.parent.mkdir(parents=True, exist_ok=True)
        self.store.path.write_text("{broken", encoding="utf-8")
        result = self.store.read()

        self.assertEqual(result.freshness, CacheFreshness.INVALID)
        self.assertFalse(result.has_data)

    def test_cache_uses_atomic_schema_envelope(self) -> None:
        self.store.save(parse_reference_snapshot(payload([])))
        raw = json.loads(self.store.path.read_text(encoding="utf-8"))

        self.assertEqual(raw["schemaVersion"], 2)
        self.assertEqual(raw["payload"]["references"], [])
        self.assertTrue(raw["generatedAt"].endswith("Z"))
        self.assertFalse(self.store.path.with_suffix(".json.tmp").exists())

    def test_status_tones_are_semantic_and_layout_widths_are_stable(self) -> None:
        positive = parse_reference_snapshot(payload()).references[0]
        negative = positive.__class__(
            **{
                **{
                    field: getattr(positive, field)
                    for field in positive.__dataclass_fields__
                },
                "status_code": "P",
                "status": "PENDIENTE DE DOCUMENTOS",
            }
        )
        neutral = positive.__class__(
            **{
                **{
                    field: getattr(positive, field)
                    for field in positive.__dataclass_fields__
                },
                "status_code": "T",
                "status": "EN TRÁMITE",
            }
        )
        delivered = positive.__class__(
            **{
                **{
                    field: getattr(positive, field)
                    for field in positive.__dataclass_fields__
                },
                "status_code": "D",
                "status": "DESPACHADO",
            }
        )
        concluded = positive.__class__(
            **{
                **{
                    field: getattr(positive, field)
                    for field in positive.__dataclass_fields__
                },
                "status_code": "C",
                "status": "PREVIO CONCLUIDO",
            }
        )
        billed = positive.__class__(
            **{
                **{
                    field: getattr(positive, field)
                    for field in positive.__dataclass_fields__
                },
                "status_code": "G",
                "status": "CUENTA DE GASTOS",
            }
        )

        self.assertEqual(
            ReferencesPanel._status_object_name(delivered),
            "statusPrePositive",
        )
        self.assertEqual(
            ReferencesPanel._status_object_name(concluded),
            "statusPrePositive",
        )
        self.assertFalse(ReferencesPanel._is_concluded(delivered))
        self.assertFalse(ReferencesPanel._is_concluded(concluded))
        self.assertEqual(
            ReferencesPanel._status_object_name(billed),
            "statusPositive",
        )
        self.assertTrue(ReferencesPanel._is_concluded(billed))
        self.assertFalse(ReferencesPanel._is_concluded(negative))
        self.assertEqual(
            ReferencesPanel._status_object_name(negative),
            "statusNegative",
        )
        self.assertEqual(
            ReferencesPanel._status_object_name(neutral),
            "statusNeutral",
        )

        panel = ReferencesPanel()
        item = panel._build_reference_item(negative)
        status = item.findChild(type(panel._count_label), "statusNegative")
        operation = item.findChild(type(panel._count_label), "operationImport")
        self.assertEqual(status.sizePolicy().horizontalPolicy().name, "Expanding")
        self.assertTrue(status.wordWrap())
        code = item.findChild(type(panel._count_label), "referenceCodeBadge")
        self.assertEqual(code.width(), panel._REFERENCE_WIDTH)
        self.assertTrue(code.wordWrap())
        self.assertEqual(operation.width(), panel._OPERATION_WIDTH)

        panel.set_references([negative])
        panel._update_column_widths(430)
        code = panel.findChild(type(panel._count_label), "referenceCodeBadge")
        operation = panel.findChild(type(panel._count_label), "operationImport")
        self.assertGreater(code.width(), panel._REFERENCE_WIDTH)
        self.assertGreater(operation.width(), panel._OPERATION_WIDTH)

    def test_counter_excludes_prepositive_statuses(self) -> None:
        original = parse_reference_snapshot(payload()).references[0]
        references = [
            original.__class__(
                **{
                    **{
                        field: getattr(original, field)
                        for field in original.__dataclass_fields__
                    },
                    "status_code": "D",
                    "status": "DESPACHADO",
                }
            ),
            original.__class__(
                **{
                    **{
                        field: getattr(original, field)
                        for field in original.__dataclass_fields__
                    },
                    "reference_number": "VER26-01235",
                    "status_code": "C",
                    "status": "PREVIO CONCLUIDO",
                }
            ),
            original.__class__(
                **{
                    **{
                        field: getattr(original, field)
                        for field in original.__dataclass_fields__
                    },
                    "reference_number": "VER26-01236",
                    "status_code": "G",
                    "status": "CUENTA DE GASTOS",
                }
            ),
        ]
        panel = ReferencesPanel()
        panel.set_references(references)

        self.assertEqual(panel._count_label.text(), "3  -  1 concluidas")

    def test_scroll_restarts_at_real_scrollbar_limit(self) -> None:
        panel = ReferencesPanel()
        scroll_bar = panel._scroll.verticalScrollBar()
        scroll_bar.setRange(0, 20)
        scroll_bar.setValue(19)
        panel._cycle_height = 100

        panel._advance_references()

        self.assertEqual(scroll_bar.value(), 0)

    def test_scroll_catches_up_after_a_delayed_frame(self) -> None:
        panel = ReferencesPanel()
        scroll_bar = panel._scroll.verticalScrollBar()
        scroll_bar.setRange(0, 500)
        panel._cycle_height = 500

        panel._advance_references_by(102)

        self.assertEqual(scroll_bar.value(), 3)


if __name__ == "__main__":
    unittest.main()
