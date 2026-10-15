"""Open-Meteo hourly forecast adapter (no API key needed).

Docs: https://open-meteo.com/en/docs
Many coordinates go in one request (comma-separated), so a whole route's checkpoints
or a heatmap grid costs a handful of HTTP calls. Each location's series is cached.
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
HOURLY = "wind_speed_10m,wind_gusts_10m,rain,showers,snowfall"
CHUNK = 100  # locations per request; keeps URLs well under length limits
MAX_HORIZON = timedelta(days=15)

KMH_TO_MPH = 0.621371
MM_TO_IN = 1 / 25.4
CM_TO_IN = 1 / 2.54


def _hour_floor(dt: datetime) -> datetime:
    return dt.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def _round(p: LatLon) -> LatLon:
    # 0.01° (~1 km) is finer than the forecast models' grid, and lets nearby
    # checkpoints from different routes share a cache entry.
    return (round(p[0], 2), round(p[1], 2))


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
        start_h = _hour_floor(start)
        end_h = _hour_floor(end) + timedelta(hours=1)
        if end_h - _hour_floor(datetime.now(UTC)) > MAX_HORIZON:
            raise ProviderError("Trip extends beyond the 15-day weather forecast horizon", status=400)

        window = f"{start_h:%Y%m%d%H}-{end_h:%Y%m%d%H}"
        rounded = [_round(p) for p in points]
        unique = list(dict.fromkeys(rounded))
        keys = {p: f"om:{p[0]:.2f}:{p[1]:.2f}:{window}" for p in unique}
        found: dict[LatLon, HourlySeries] = {}
        cached = cache.get_many(list(keys.values()))
        for p, k in keys.items():
            if k in cached:
                found[p] = cached[k]

        missing = [p for p in unique if p not in found]
        for i in range(0, len(missing), CHUNK):
            chunk = missing[i : i + CHUNK]
            params = {
                "latitude": ",".join(f"{p[0]:.2f}" for p in chunk),
                "longitude": ",".join(f"{p[1]:.2f}" for p in chunk),
                "hourly": HOURLY,
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "timezone": "GMT",
                "timeformat": "unixtime",
                "start_hour": f"{start_h:%Y-%m-%dT%H:%M}",
                "end_hour": f"{end_h:%Y-%m-%dT%H:%M}",
            }
            payload = get_json(URL, params, service="Open-Meteo")
            items = payload if isinstance(payload, list) else [payload]
            if len(items) != len(chunk):
                raise ProviderError("Open-Meteo returned an unexpected number of locations")
            fresh = {}
            for p, item in zip(chunk, items):
                found[p] = parse_location(item)
                fresh[keys[p]] = found[p]
            cache.set_many(fresh, timeout=settings.WEATHER_CACHE_SECONDS)

        return [found[p] for p in rounded]
