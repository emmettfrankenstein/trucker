"""Place weather checkpoints along a route and work out when the truck reaches each."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .geo import METERS_PER_MILE, LatLon, cumulative_miles, interp, point_at_mile

ALLOWED_INTERVALS_MI = (10, 25, 50)


@dataclass(frozen=True)
class SampledPoint:
    seq: int
    mile: float
    lat: float
    lon: float
    offset_s: float  # seconds after departure
    span_start_mi: float  # the stretch of road this checkpoint represents
    span_end_mi: float

    @property
    def span_mi(self) -> float:
        return self.span_end_mi - self.span_start_mi


def time_curve(
    total_miles: float,
    total_seconds: float,
    anchors: Sequence[tuple[float, float]] = (),
) -> tuple[list[float], list[float]]:
    """Build a monotonic (miles, seconds) curve for ETA interpolation.

    ``anchors`` are (meters from origin, seconds from departure) pairs taken from the
    router's turn-by-turn guidance, so slow urban stretches get realistic ETAs instead
    of assuming an average speed for the whole trip.
    """
    miles, secs = [0.0], [0.0]
    for meters, seconds in sorted(anchors):
        m = meters / METERS_PER_MILE
        if m > miles[-1] and seconds >= secs[-1] and m < total_miles:
            miles.append(m)
            secs.append(float(seconds))
    miles.append(total_miles)
    secs.append(max(float(total_seconds), secs[-1]))
    return miles, secs


def sample_route(
    points: Sequence[LatLon],
    interval_mi: float,
    total_seconds: float,
    anchors: Sequence[tuple[float, float]] = (),
    route_miles: float | None = None,
) -> list[SampledPoint]:
    """Checkpoints every ``interval_mi`` plus origin and destination.

    Each checkpoint owns the miles halfway to its neighbours, so the spans tile the
    route exactly and "miles at Severe" sums back to the route length.

    ``route_miles`` (the router's reported length) rescales the geometric length, which
    is slightly shorter than the driven distance after polyline simplification.
    """
    if interval_mi <= 0:
        raise ValueError("interval must be positive")
    if len(points) < 2:
        raise ValueError("route needs at least two points")

    cum = cumulative_miles(points)
    geo_total = cum[-1]
    total = route_miles if route_miles and geo_total > 0 else geo_total
    scale = total / geo_total if geo_total else 1.0

    marks = [0.0]
    m = interval_mi
    while m < total - 1e-9:
        marks.append(m)
        m += interval_mi
    if total > 0:
        marks.append(total)

    curve_m, curve_s = time_curve(total, total_seconds, anchors)
    out: list[SampledPoint] = []
    for i, mile in enumerate(marks):
        lat, lon = point_at_mile(points, cum, mile / scale)
        start = 0.0 if i == 0 else (marks[i - 1] + mile) / 2
        end = total if i == len(marks) - 1 else (mile + marks[i + 1]) / 2
        out.append(
            SampledPoint(
                seq=i,
                mile=mile,
                lat=lat,
                lon=lon,
                offset_s=interp(mile, curve_m, curve_s),
                span_start_mi=start,
                span_end_mi=end,
            )
        )
    return out
