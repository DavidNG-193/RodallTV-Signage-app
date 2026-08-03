from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class DailyReference:
    id: str
    code: str
    description: str
    sequence: int
    location: str = ""
    operation_type: str = "Importación"
    status: str = "EN TRÁMITE"
