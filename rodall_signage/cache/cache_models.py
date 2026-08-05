from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Generic, TypeVar


T = TypeVar("T")


class CacheFreshness(StrEnum):
    FRESH = "Fresh"
    EXPIRED = "Expired"
    MISSING = "Missing"
    INVALID = "Invalid"


@dataclass(frozen=True, slots=True)
class CacheEnvelope(Generic[T]):
    schema_version: int
    generated_at: datetime
    expires_at: datetime | None
    payload: T

    def freshness(self, now: datetime | None = None) -> CacheFreshness:
        current = now or datetime.now(timezone.utc)
        current = (
            current.replace(tzinfo=timezone.utc)
            if current.tzinfo is None
            else current.astimezone(timezone.utc)
        )

        if self.expires_at is None:
            return CacheFreshness.FRESH

        expires_at = (
            self.expires_at.replace(tzinfo=timezone.utc)
            if self.expires_at.tzinfo is None
            else self.expires_at.astimezone(timezone.utc)
        )

        if current >= expires_at:
            return CacheFreshness.EXPIRED

        return CacheFreshness.FRESH


@dataclass(frozen=True, slots=True)
class CacheReadResult(Generic[T]):
    freshness: CacheFreshness
    envelope: CacheEnvelope[T] | None
    message: str | None = None

    @property
    def has_data(self) -> bool:
        return self.envelope is not None
