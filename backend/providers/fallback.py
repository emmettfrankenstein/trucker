"""Weather from the first provider in WEATHER_PROVIDER_CHAIN that is available.

A provider that is out of quota is skipped until its quota resets, so a busy hour costs one
refused request rather than one per trip.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime

from django.conf import settings
from django.core.cache import cache
from django.utils.module_loading import import_string

from trips.domain.geo import LatLon
from trips.domain.weather import HourlySeries

from .base import ProviderError

logger = logging.getLogger(__name__)


class FallbackWeather:
    def hourly(self, points: Sequence[LatLon], start: datetime, end: datetime) -> list[HourlySeries]:
        error: ProviderError | None = None
        for path in settings.WEATHER_PROVIDER_CHAIN:
            resting = f"weather:resting:{path}"
            if cache.get(resting):
                continue
            try:
                return import_string(path)().hourly(points, start, end)
            except ProviderError as exc:
                if not exc.unavailable:
                    raise
                logger.warning("%s unavailable, trying the next weather source: %s", path, exc)
                if exc.retry_after:
                    cache.set(resting, True, timeout=exc.retry_after)
                error = error or exc
        raise error or ProviderError(
            "Weather forecasts are unavailable right now. Please try again in a few minutes.", status=503
        )
