from datetime import date, datetime
from typing import Any

from rodall_signage.models.reference import (
    ReferenceItem,
    ReferenceSnapshot,
)

def _parse_utc_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("La fecha UTC debe ser texto.")

    parsed = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )
    if parsed.tzinfo is None:
        raise ValueError("La fecha UTC debe incluir zona horaria.")
    return parsed


def _required_text(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} es obligatorio.")
    return value.strip()

def parse_reference_snapshot(
    payload: dict[str, Any],
) -> ReferenceSnapshot:
    fetched_at = _parse_utc_datetime(
        payload.get("fetchedAtUtc")
    )

    raw_references = payload.get("references")

    if not isinstance(raw_references, list):
        raise ValueError("references debe ser una lista.")

    parsed: list[ReferenceItem] = []

    for raw in raw_references:
        if not isinstance(raw, dict):
            raise ValueError(
                "Cada referencia debe ser un objeto."
            )

        try:
            parsed.append(
                ReferenceItem(
                    id=_required_text(raw, "id"),
                    reference_number=_required_text(raw, "referenceNumber"),
                    reference_date=date.fromisoformat(
                        str(raw["referenceDate"])
                    ),
                    client=_required_text(raw, "client"),
                    operation_code=_required_text(raw, "operationCode"),
                    operation=_required_text(raw, "operation"),
                    document=_required_text(raw, "document"),
                    customs_office_number=int(
                        raw["customsOfficeNumber"]
                    ),
                    customs_office=_required_text(raw, "customsOffice"),
                    status_code=_required_text(raw, "statusCode"),
                    status=_required_text(raw, "status"),
                    last_external_update_at=_parse_utc_datetime(
                        raw["lastExternalUpdateAt"]
                    ),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                "La referencia contiene datos inválidos."
            ) from exc

    return ReferenceSnapshot(
        fetched_at_utc=fetched_at,
        references=tuple(parsed),
    )
