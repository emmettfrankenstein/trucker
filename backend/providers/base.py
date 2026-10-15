"""Provider-neutral types. Swapping TomTom or Open-Meteo for another vendor means
writing one adapter that returns these; nothing in the domain or API layer changes."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from trips.domain.geo import LatLon
from trips.domain.weather import HourlySeries


class ProviderError(Exception):
    """An upstream API failed or returned something we cannot use."""

    def __init__(self, message: str, *, status: int = 502, retry_after: int | None = None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after  # seconds until a rate-limited service may work again

    @property
    def unavailable(self) -> bool:
        """The service is down or out of quota, as opposed to rejecting this input."""
        return self.status >= 500


@dataclass(frozen=True)
class RoutePlan:
    points: list[LatLon]
    distance_m: float
    duration_s: float
    # (meters from origin, seconds from departure) pairs from turn-by-turn guidance
    time_anchors: list[tuple[float, float]] = field(default_factory=list)
    traffic_delay_s: float = 0.0
    via: LatLon | None = None


@dataclass(frozen=True)
class Place:
    label: str
    lat: float
    lon: float


class RoutingProvider(Protocol):
    name: str

    def routes(
        self,
        origin: LatLon,
        destination: LatLon,
        *,
        depart_at: datetime,
        load_lb: float,
        alternatives: int = 2,
        via: LatLon | None = None,
    ) -> list[RoutePlan]: ...


class GeocodingProvider(Protocol):
    def search(self, query: str, *, limit: int = 6) -> list[Place]: ...


class WeatherProvider(Protocol):
    def hourly(self, points: Sequence[LatLon], start: datetime, end: datetime) -> list[HourlySeries]: ...
