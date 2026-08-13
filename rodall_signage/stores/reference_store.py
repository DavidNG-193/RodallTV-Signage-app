from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from rodall_signage.cache.cache_models import CacheReadResult
from rodall_signage.cache.json_cache_store import JsonCacheStore
from rodall_signage.models import ReferenceItem, ReferenceSnapshot


class ReferenceStore:
    SCHEMA_VERSION = 2

    def __init__(
        self,
        path: Path,
        cache_lifetime_seconds: int = 300,
    ) -> None:
        self._cache_lifetime = timedelta(
            seconds=max(cache_lifetime_seconds, 300)
        )
        self._cache = JsonCacheStore[ReferenceSnapshot](
            path=path,
            schema_version=self.SCHEMA_VERSION,
            serialize_payload=self._serialize,
            parse_payload=self._parse,
        )

    @property
    def path(self) -> Path:
        return self._cache.path

    def read(self) -> CacheReadResult[ReferenceSnapshot]:
        return self._cache.read()

    def save(self, snapshot: ReferenceSnapshot) -> None:
        fetched_at = snapshot.fetched_at_utc.astimezone(timezone.utc)
        self._cache.write_atomic(
            snapshot,
            generated_at=fetched_at,
            expires_at=fetched_at + self._cache_lifetime,
        )

    def delete(self) -> None:
        self._cache.delete()

    @staticmethod
    def _serialize(snapshot: ReferenceSnapshot) -> object:
        return {
            "fetchedAtUtc": ReferenceStore._format_utc(
                snapshot.fetched_at_utc
            ),
            "references": [
                {
                    "id": item.id,
                    "referenceNumber": item.reference_number,
                    "referenceDate": item.reference_date.isoformat(),
                    "client": item.client,
                    "operationCode": item.operation_code,
                    "operation": item.operation,
                    "document": item.document,
                    "customsOfficeNumber": item.customs_office_number,
                    "customsOffice": item.customs_office,
                    "statusCode": item.status_code,
                    "status": item.status,
                    "lastExternalUpdateAt": ReferenceStore._format_utc(
                        item.last_external_update_at
                    ),
                }
                for item in snapshot.references
            ],
        }

    @staticmethod
    def _parse(payload: object) -> ReferenceSnapshot:
        if not isinstance(payload, dict):
            raise TypeError("El payload de referencias debe ser un objeto.")

        fetched_at = ReferenceStore._parse_utc(payload.get("fetchedAtUtc"))
        raw_references = payload.get("references")
        if not isinstance(raw_references, list):
            raise TypeError("references debe ser una lista.")

        references: list[ReferenceItem] = []
        seen_ids: set[str] = set()

        for raw in raw_references:
            if not isinstance(raw, dict):
                raise TypeError("Cada referencia debe ser un objeto.")

            try:
                item = ReferenceItem(
                    id=ReferenceStore._required_text(raw, "id"),
                    reference_number=ReferenceStore._required_text(
                        raw, "referenceNumber"
                    ),
                    reference_date=date.fromisoformat(
                        ReferenceStore._required_text(raw, "referenceDate")
                    ),
                    client=ReferenceStore._required_text(raw, "client"),
                    operation_code=ReferenceStore._required_text(
                        raw, "operationCode"
                    ),
                    operation=ReferenceStore._required_text(raw, "operation"),
                    document=ReferenceStore._required_text(raw, "document"),
                    customs_office_number=int(raw["customsOfficeNumber"]),
                    customs_office=ReferenceStore._required_text(
                        raw, "customsOffice"
                    ),
                    status_code=ReferenceStore._required_text(
                        raw, "statusCode"
                    ),
                    status=ReferenceStore._required_text(raw, "status"),
                    last_external_update_at=ReferenceStore._parse_utc(
                        raw.get("lastExternalUpdateAt")
                    ),
                )
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(
                    "La referencia almacenada contiene datos inválidos."
                ) from error

            if item.id in seen_ids:
                raise ValueError("Las referencias contienen ids duplicados.")
            seen_ids.add(item.id)
            references.append(item)

        return ReferenceSnapshot(fetched_at, tuple(references))

    @staticmethod
    def _required_text(raw: dict, key: str) -> str:
        value = raw.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} es obligatorio.")
        return value.strip()

    @staticmethod
    def _parse_utc(value: object) -> datetime:
        if not isinstance(value, str) or not value.strip():
            raise TypeError("La fecha UTC debe ser texto.")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("La fecha UTC debe incluir zona horaria.")
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _format_utc(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
