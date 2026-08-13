from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class ReferenceItem:
    id: str
    reference_number: str
    reference_date: date
    client: str
    operation_code: str
    operation: str
    document: str
    customs_office_number: int
    customs_office: str
    status_code: str
    status: str
    last_external_update_at: datetime


@dataclass(frozen=True, slots=True)
class ReferenceSnapshot:
    fetched_at_utc: datetime
    references: tuple[ReferenceItem, ...]

    def __len__(self) -> int:
        return len(self.references)
