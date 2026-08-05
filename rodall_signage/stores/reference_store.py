from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rodall_signage.cache.cache_models import CacheReadResult
from rodall_signage.cache.json_cache_store import JsonCacheStore
from rodall_signage.models import DailyReference


class ReferenceStore:
    SCHEMA_VERSION = 1

    def __init__(self, path: Path) -> None:
        self._cache = JsonCacheStore[list[DailyReference]](
            path=path,
            schema_version=self.SCHEMA_VERSION,
            serialize_payload=self._serialize,
            parse_payload=self._parse,
        )

    @property
    def path(self) -> Path:
        return self._cache.path

    def read(self) -> CacheReadResult[list[DailyReference]]:
        return self._cache.read()

    def write(
        self,
        references: list[DailyReference],
        generated_at: datetime,
        expires_at: datetime | None,
    ) -> None:
        self._cache.write_atomic(list(references), generated_at, expires_at)

    def delete(self) -> None:
        self._cache.delete()

    @staticmethod
    def _serialize(references: list[DailyReference]) -> object:
        return [
            {
                "id": reference.id,
                "code": reference.code,
                "description": reference.description,
                "sequence": reference.sequence,
                "location": reference.location,
                "operationType": reference.operation_type,
                "status": reference.status,
            }
            for reference in references
        ]

    @staticmethod
    def _parse(payload: object) -> list[DailyReference]:
        if not isinstance(payload, list):
            raise TypeError("El payload de referencias debe ser una lista.")

        references: list[DailyReference] = []
        seen_ids: set[str] = set()
        seen_sequences: set[int] = set()

        for raw in payload:
            if not isinstance(raw, dict):
                raise TypeError("Cada referencia debe ser un objeto.")

            reference_id = ReferenceStore._required_text(raw, "id")
            sequence = raw["sequence"]
            if type(sequence) is not int or sequence < 0:
                raise ValueError("sequence debe ser un entero no negativo.")
            if reference_id in seen_ids or sequence in seen_sequences:
                raise ValueError(
                    "Las referencias contienen ids o secuencias duplicadas."
                )

            seen_ids.add(reference_id)
            seen_sequences.add(sequence)
            references.append(
                DailyReference(
                    id=reference_id,
                    code=ReferenceStore._required_text(raw, "code"),
                    description=ReferenceStore._required_text(
                        raw,
                        "description",
                    ),
                    sequence=sequence,
                    location=ReferenceStore._optional_text(raw, "location"),
                    operation_type=ReferenceStore._required_text(
                        raw,
                        "operationType",
                    ),
                    status=ReferenceStore._required_text(raw, "status"),
                )
            )

        return sorted(references, key=lambda item: item.sequence)

    @staticmethod
    def _required_text(raw: dict, key: str) -> str:
        value = raw[key]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} es obligatorio.")
        return value.strip()

    @staticmethod
    def _optional_text(raw: dict, key: str) -> str:
        value = raw.get(key, "")
        if not isinstance(value, str):
            raise TypeError(f"{key} debe ser texto.")
        return value.strip()
