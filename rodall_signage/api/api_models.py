from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class SyncResult(StrEnum):
    SUCCESS = "Success"
    FAILED = "Failed"
    NO_CHANGES = "NoChanges"


@dataclass(frozen=True, slots=True)
class AssignmentStatus:
    has_assignment: bool
    playlist_id: str | None
    playlist_version: int
    requires_sync: bool


@dataclass(frozen=True, slots=True)
class HeartbeatResult:
    server_time: str | None
    pending_power_command: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class SyncReport:
    result: SyncResult
    playlist_id: str | None
    synced_version: int
    message: str | None
    downloaded_files_count: int
    deleted_files_count: int
    started_at: datetime
    finished_at: datetime
