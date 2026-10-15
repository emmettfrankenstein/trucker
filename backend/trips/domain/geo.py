"""Small geometry helpers: distances, interpolation and polyline encoding."""

from __future__ import annotations

import itertools
import math
from bisect import bisect_right
from collections.abc import Sequence

EARTH_RADIUS_MI = 3958.7613
METERS_PER_MILE = 1609.344

LatLon = tuple[float, float]


def haversine_mi(a: LatLon, b: LatLon) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(h))


def cumulative_miles(points: Sequence[LatLon]) -> list[float]:
    out = [0.0]
    for prev, cur in itertools.pairwise(points):
        out.append(out[-1] + haversine_mi(prev, cur))
    return out


def interp(x: float, xs: Sequence[float], ys: Sequence[float]) -> float:
    """Piecewise-linear interpolation, clamped at both ends. ``xs`` must be ascending."""
    if not xs:
        raise ValueError("empty series")
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    i = bisect_right(xs, x)
    x0, x1, y0, y1 = xs[i - 1], xs[i], ys[i - 1], ys[i]
    if x1 == x0:
        return y1
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def point_at_mile(points: Sequence[LatLon], cum: Sequence[float], mile: float) -> LatLon:
    if mile <= 0:
        return points[0]
    if mile >= cum[-1]:
        return points[-1]
    i = bisect_right(cum, mile)
    seg = cum[i] - cum[i - 1]
    t = 0.0 if seg == 0 else (mile - cum[i - 1]) / seg
    (lat0, lon0), (lat1, lon1) = points[i - 1], points[i]
    return (lat0 + (lat1 - lat0) * t, lon0 + (lon1 - lon0) * t)


# --- Google encoded polyline (precision 5) -----------------------------------------


def _encode_value(v: int) -> str:
    v = ~(v << 1) if v < 0 else v << 1
    chunks = []
    while v >= 0x20:
        chunks.append(chr((0x20 | (v & 0x1F)) + 63))
        v >>= 5
    chunks.append(chr(v + 63))
    return "".join(chunks)


def encode_polyline(points: Sequence[LatLon]) -> str:
    out, prev_lat, prev_lon = [], 0, 0
    for lat, lon in points:
        ilat, ilon = round(lat * 1e5), round(lon * 1e5)
        out.append(_encode_value(ilat - prev_lat))
        out.append(_encode_value(ilon - prev_lon))
        prev_lat, prev_lon = ilat, ilon
    return "".join(out)


def decode_polyline(encoded: str) -> list[LatLon]:
    points, index, lat, lon = [], 0, 0, 0
    while index < len(encoded):
        deltas = []
        for _ in range(2):
            shift = result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        lat += deltas[0]
        lon += deltas[1]
        points.append((lat / 1e5, lon / 1e5))
    return points


def simplify_by_distance(points: Sequence[LatLon], min_gap_mi: float = 0.05) -> list[LatLon]:
    """Drop vertices closer than ``min_gap_mi`` to the last kept one (keeps payloads small)."""
    if len(points) < 3:
        return list(points)
    kept = [points[0]]
    for p in points[1:-1]:
        if haversine_mi(kept[-1], p) >= min_gap_mi:
            kept.append(p)
    kept.append(points[-1])
    return kept
