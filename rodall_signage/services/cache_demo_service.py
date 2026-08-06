from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging

from rodall_signage.cache.cache_registry import CacheRegistry
from rodall_signage.services.demo_data_service import DemoDataService


logger = logging.getLogger(__name__)


class CacheDemoService:
    def __init__(self, registry: CacheRegistry) -> None:
        self._registry = registry

    def seed(self) -> None:
        generated_at = datetime.now(timezone.utc)
        writes = (
            (
                "clima",
                lambda: self._registry.weather.write(
                    DemoDataService.weather(),
                    generated_at,
                    generated_at + timedelta(minutes=30),
                ),
            ),
            (
                "referencias",
                lambda: self._registry.references.write(
                    DemoDataService.references(),
                    generated_at,
                    generated_at + timedelta(days=1),
                ),
            ),
        )

        for name, write in writes:
            try:
                write()
            except Exception:
                logger.exception("No fue posible sembrar la caché de %s.", name)

    def log_status(self) -> None:
        stores = (
            ("clima", self._registry.weather),
            ("referencias", self._registry.references),
        )

        for name, store in stores:
            result = store.read()
            logger.info(
                "Estado de caché. name=%s freshness=%s has_data=%s "
                "message=%s",
                name,
                result.freshness.value,
                result.has_data,
                result.message,
            )
