"""Open-Meteo hourly forecast adapter.

Docs: https://open-meteo.com/en/docs
Many coordinates go in one request (comma-separated), so a whole route's checkpoints
or a heatmap grid costs a handful of HTTP calls. Each location's series is cached.

The free tier counts every location as one call and allows about 600 a minute, so we:
  * snap lookups to a lattice (0.1° by default, about the forecast models' resolution)
    so overlapping routes and the heatmap share locations;
  * coarsen that lattice for very long trips so one request stays within budget;
  * keep a shared per-minute budget (in the cache, so it spans workers) and fail fast
    with a clear message instead of burning quota on a request that will be refused.
Setting OPEN_METEO_API_KEY switches to the commercial endpoint, which removes the limits.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from django.conf import settings
from django.core.cache import cache

from trips.domain.geo import LatLon
from trips.domain.weather import HourlySeries

from .base import ProviderError
from .http import get_json

URL = "https://api.open-meteo.com/v1/forecast"
CUSTOMER_URL = "https://customer-api.open-meteo.com/v1/forecast"
HOURLY = "wind_speed_10m,wind_gusts_10m,rain,showers,snowfall"
CHUNK = 100  # locations per request; keeps URLs well under length limits
MAX_HORIZON = timedelta(days=15)
LATTICES_DEG = (0.1, 0.15, 0.2, 0.25, 0.35, 0.5)
MIN_WINDOW = timedelta(hours=49)

KMH_TO_MPH = 0.621371
MM_TO_IN = 1 / 25.4
CM_TO_IN = 1 / 2.54


def _hour_floor(dt: datetime) -> datetime:
    return dt.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def _snap(p: LatLon, step: float) -> LatLon:
    return (round(round(p[0] / step) * step, 3), round(round(p[1] / step) * step, 3))


def choose_lattice(points: Sequence[LatLon], max_locations: int) -> float:
    """Finest lattice whose unique snapped locations fit in one request's budget."""
    for step in LATTICES_DEG:
        if len({_snap(p, step) for p in points}) <= max_locations:
            return step
    return LATTICES_DEG[-1]


def _window(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    """Hour-aligned window, padded to whole days of at least 49 h.

    Standard windows mean a trip's checkpoints and its 0-48 h heatmap ask for the same
    time span, so any shared location is fetched once and served from cache after.
    """
    start_h = _hour_floor(start)
    needed = max(_hour_floor(end) + timedelta(hours=1) - start_h, MIN_WINDOW)
    days = -(-needed // timedelta(days=1))
    return start_h, start_h + days * timedelta(days=1)


def _budgets(now: datetime) -> list[tuple[str, int, int, int]]:
    """(cache key, limit, key lifetime, seconds until reset) for each free-tier window."""
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    next_day = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return [
        (f"om:budget:m:{now:%Y%m%d%H%M}", settings.OPEN_METEO_LOCATIONS_PER_MINUTE, 120, 60 - now.second),
        (f"om:budget:h:{now:%Y%m%d%H}", settings.OPEN_METEO_LOCATIONS_PER_HOUR, 7200, (next_hour - now).seconds),
        (f"om:budget:d:{now:%Y%m%d}", settings.OPEN_METEO_LOCATIONS_PER_DAY, 2 * 86400, (next_day - now).seconds),
    ]


def _reserve_budget(count: int) -> None:
    """Count locations against the shared minute, hour and day budgets, or refuse up front."""
    if settings.OPEN_METEO_API_KEY or count == 0:
        return
    taken: list[str] = []
    for key, limit, ttl, resets_in in _budgets(datetime.now(UTC)):
        if not limit:
            continue
        cache.add(key, 0, timeout=ttl)
        try:
            used = cache.incr(key, count)
        except ValueError:  # key evicted between add and incr
            cache.set(key, count, timeout=ttl)
            used = count
        taken.append(key)
        if used > limit:
            for k in taken:
                cache.decr(k, count)
            raise ProviderError(
                "The free weather service is at its usage limit. Please try again in about a minute.",
                status=503,
                retry_after=max(resets_in, 1),
            )


def _convert(values: list, unit: str) -> list[float]:
    factor = {"km/h": KMH_TO_MPH, "mm": MM_TO_IN, "cm": CM_TO_IN}.get(unit, 1.0)
    return [float(v or 0.0) * factor for v in values]


def parse_location(item: dict) -> HourlySeries:
    hourly, units = item["hourly"], item.get("hourly_units", {})
    rain = _convert(hourly["rain"], units.get("rain", "inch"))
    showers = _convert(hourly.get("showers", [0] * len(rain)), units.get("showers", "inch"))
    return HourlySeries(
        times=[float(t) for t in hourly["time"]],
        wind_mph=_convert(hourly["wind_speed_10m"], units.get("wind_speed_10m", "mp/h")),
        gust_mph=_convert(hourly["wind_gusts_10m"], units.get("wind_gusts_10m", "mp/h")),
        rain_in_hr=[r + s for r, s in zip(rain, showers)],
        snow_in_hr=_convert(hourly["snowfall"], units.get("snowfall", "inch")),
    )


class OpenMeteoWeather:
    def hourly(self, points: Sequence[LatLon], start: datetime, end: datetime) -> list[HourlySeries]:
        start_h, end_h = _window(start, end)
        if end_h - _hour_floor(datetime.now(UTC)) > MAX_HORIZON:
            raise ProviderError("Trip extends beyond the 15-day weather forecast horizon", status=400)

        step = choose_lattice(points, settings.OPEN_METEO_MAX_LOCATIONS_PER_REQUEST)
        window = f"{start_h:%Y%m%d%H}-{end_h:%Y%m%d%H}"
        snapped = [_snap(p, step) for p in points]
        unique = list(dict.fromkeys(snapped))
        keys = {p: f"om:{p[0]:.3f}:{p[1]:.3f}:{window}" for p in unique}
        found: dict[LatLon, HourlySeries] = {}
        cached = cache.get_many(list(keys.values()))
        for p, k in keys.items():
            if k in cached:
                found[p] = cached[k]

        missing = [p for p in unique if p not in found]
        _reserve_budget(len(missing))
        url, extra = (
            (CUSTOMER_URL, {"apikey": settings.OPEN_METEO_API_KEY}) if settings.OPEN_METEO_API_KEY else (URL, {})
        )
        for i in range(0, len(missing), CHUNK):
            chunk = missing[i : i + CHUNK]
            params = {
                "latitude": ",".join(f"{p[0]:.3f}" for p in chunk),
                "longitude": ",".join(f"{p[1]:.3f}" for p in chunk),
                "hourly": HOURLY,
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "timezone": "GMT",
                "timeformat": "unixtime",
                "start_hour": f"{start_h:%Y-%m-%dT%H:%M}",
                "end_hour": f"{end_h:%Y-%m-%dT%H:%M}",
                **extra,
            }
            payload = get_json(url, params, service="Open-Meteo")
            items = payload if isinstance(payload, list) else [payload]
            if len(items) != len(chunk):
                raise ProviderError("Open-Meteo returned an unexpected number of locations")
            fresh = {}
            for p, item in zip(chunk, items):
                found[p] = parse_location(item)
                fresh[keys[p]] = found[p]
            cache.set_many(fresh, timeout=settings.WEATHER_CACHE_SECONDS)

        return [found[p] for p in snapped]
