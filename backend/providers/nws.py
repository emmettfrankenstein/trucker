"""US National Weather Service adapter (api.weather.gov), the primary source for US points.

Docs: https://www.weather.gov/documentation/services-web-api
Free and keyless; it asks only for an identifying User-Agent. Two steps per location:
``/points/{lat},{lon}`` names the forecast office grid cell that covers it (fixed, so it is
cached for weeks), and that cell's ``forecastGridData`` holds hourly-or-coarser layers for
wind, gusts, liquid precipitation and snowfall. Nearby points share a cell, and each cell's
parsed forecast is cached, so a repeat trip costs nothing.

Points outside NWS coverage (Canada, Mexico) come back as None for the next source to fill.
A cell that fails to load does the same, so one bad cell never sinks a whole trip.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from django.conf import settings
from django.core.cache import cache

from trips.domain.geo import LatLon
from trips.domain.weather import HourlySeries

from .base import ProviderError
from .http import get_json
from .openmeteo import _snap, choose_lattice

logger = logging.getLogger(__name__)

POINTS_URL = "https://api.weather.gov/points/{0},{1}"  # 4 decimals at most, no trailing zeros
POINT_CACHE_SECONDS = 30 * 86400
OUTSIDE = ""  # cached marker: NWS does not cover this point
TO_MPH = {"wmoUnit:km_h-1": 0.621371, "wmoUnit:m_s-1": 2.236936, "wmoUnit:mi_h-1": 1.0}
TO_MM = {"wmoUnit:mm": 1.0, "wmoUnit:cm": 10.0, "wmoUnit:m": 1000.0}
SNOW_TO_WATER = 0.1  # 10:1 snow-to-liquid ratio, to keep snow's water out of "rain"
_DURATION = re.compile(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?")


def _coord(x: float) -> str:
    return f"{x:.4f}".rstrip("0").rstrip(".")


def _period(valid_time: str) -> tuple[int, int]:
    """'2026-10-15T12:00:00+00:00/PT6H' -> (start unix seconds, length in whole hours)."""
    start, duration = valid_time.split("/")
    m = _DURATION.fullmatch(duration)
    days, hours = (int(m.group(1) or 0), int(m.group(2) or 0)) if m else (0, 1)
    return int(datetime.fromisoformat(start).timestamp()), max(days * 24 + hours, 1)


def _hourly(props: dict, name: str, units: dict[str, float], *, per_hour: bool) -> dict[int, float]:
    """Expand one grid layer to {hour: value}; totals over a period are spread evenly."""
    layer = props.get(name) or {}
    factor = units.get(layer.get("uom", ""), 1.0)
    out: dict[int, float] = {}
    for v in layer.get("values", []):
        t0, n = _period(v["validTime"])
        value = float(v.get("value") or 0.0) * factor
        if per_hour:
            value /= n
        for i in range(n):
            out[t0 + 3600 * i] = value
    return out


def parse_grid(props: dict) -> HourlySeries | None:
    wind = _hourly(props, "windSpeed", TO_MPH, per_hour=False)
    if not wind:
        return None
    gust = _hourly(props, "windGust", TO_MPH, per_hour=False)
    precip_mm = _hourly(props, "quantitativePrecipitation", TO_MM, per_hour=True)
    snow_mm = _hourly(props, "snowfallAmount", TO_MM, per_hour=True)
    times = sorted(wind)
    return HourlySeries(
        times=[float(t) for t in times],
        wind_mph=[wind[t] for t in times],
        gust_mph=[max(gust.get(t, 0.0), wind[t]) for t in times],
        rain_in_hr=[max(precip_mm.get(t, 0.0) - snow_mm.get(t, 0.0) * SNOW_TO_WATER, 0.0) / 25.4 for t in times],
        snow_in_hr=[snow_mm.get(t, 0.0) / 25.4 for t in times],
    )


class NwsWeather:
    def hourly(self, points: Sequence[LatLon], start: datetime, end: datetime) -> list[HourlySeries | None]:
        step = max(choose_lattice(points, settings.NWS_MAX_LOCATIONS), 0.1)
        snapped = [_snap(p, step) for p in points]
        unique = list(dict.fromkeys(snapped))
        with ThreadPoolExecutor(max_workers=settings.NWS_WORKERS) as pool:
            grids = dict(zip(unique, pool.map(self._grid_url, unique)))
            urls = sorted({u for u in grids.values() if u})
            series = dict(zip(urls, pool.map(self._grid_series, urls)))
        return [series.get(grids[p]) if grids[p] else None for p in snapped]

    @staticmethod
    def _grid_url(p: LatLon) -> str | None:
        key = f"nws:pt:{p[0]:.3f}:{p[1]:.3f}"
        url = cache.get(key)
        if url is not None:
            return url or None
        try:
            payload = get_json(POINTS_URL.format(*(_coord(x) for x in p)), {}, service="NWS")
        except ProviderError as exc:
            if exc.upstream_status == 404:  # outside the US
                cache.set(key, OUTSIDE, timeout=POINT_CACHE_SECONDS)
            else:
                logger.warning("NWS point lookup failed for %s: %s", p, exc)
            return None
        url = (payload.get("properties") or {}).get("forecastGridData") or OUTSIDE
        cache.set(key, url, timeout=POINT_CACHE_SECONDS)
        return url or None

    @staticmethod
    def _grid_series(url: str) -> HourlySeries | None:
        key = f"nws:grid:{url}"
        if (hit := cache.get(key)) is not None:
            return hit
        try:
            series = parse_grid(get_json(url, {}, service="NWS")["properties"])
        except (ProviderError, KeyError, TypeError, ValueError) as exc:
            logger.warning("NWS grid %s unusable: %s", url, exc)
            return None
        if series:
            cache.set(key, series, timeout=settings.WEATHER_CACHE_SECONDS)
        return series
