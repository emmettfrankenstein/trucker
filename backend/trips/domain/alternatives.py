"""Make sure we end up with three genuinely different routes.

Routers often return fewer alternatives than asked for (short trips, sparse road
networks). When that happens we force a detour by routing through a via-point
pushed sideways from the main route's midpoint, then drop any candidate that mostly
retraces a route we already have.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from .geo import LatLon, cumulative_miles, haversine_mi, point_at_mile


def _offset(p: LatLon, bearing_rad: float, miles: float) -> LatLon:
    lat = p[0] + (miles / 69.0) * math.cos(bearing_rad)
    lon = p[1] + (miles / (69.0 * max(math.cos(math.radians(p[0])), 0.2))) * math.sin(bearing_rad)
    return (lat, lon)


def via_candidates(origin: LatLon, destination: LatLon, main_route: Sequence[LatLon]) -> list[LatLon]:
    """Points left and right of the main route's midpoint, scaled to trip length."""
    crow = haversine_mi(origin, destination)
    if crow < 5:
        return []
    cum = cumulative_miles(main_route)
    mid = point_at_mile(main_route, cum, cum[-1] / 2)
    heading = math.atan2(
        (destination[1] - origin[1]) * math.cos(math.radians(origin[0])),
        destination[0] - origin[0],
    )
    shift = min(max(crow * 0.15, 8.0), 80.0)
    out = []
    for factor in (1.0, 1.8):
        for side in (math.pi / 2, -math.pi / 2):
            out.append(_offset(mid, heading + side, shift * factor))
    return out


def overlap_ratio(candidate: Sequence[LatLon], existing: Sequence[LatLon], tolerance_mi: float = 1.0) -> float:
    """Share of ``candidate`` (sampled) that runs within ``tolerance_mi`` of ``existing``."""
    if not candidate or not existing:
        return 0.0
    step = max(1, len(candidate) // 60)
    sample = candidate[::step]
    ref = existing[:: max(1, len(existing) // 400)]
    near = sum(1 for p in sample if min(haversine_mi(p, q) for q in ref) <= tolerance_mi)
    return near / len(sample)


def is_distinct(candidate: Sequence[LatLon], others: Sequence[Sequence[LatLon]], max_overlap: float = 0.85) -> bool:
    return all(overlap_ratio(candidate, o) < max_overlap for o in others)
