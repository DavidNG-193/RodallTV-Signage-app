from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MpvState(StrEnum):
    STOPPED = "Stopped"
    STARTING = "Starting"
    READY = "Ready"
    PLAYING = "Playing"
    ERROR = "Error"


@dataclass(frozen=True, slots=True)
class MpvEvent:
    name: str
    data: object | None = None
    raw: dict | None = None