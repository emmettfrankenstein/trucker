"""MET Norway Locationforecast adapter, the fallback when Open-Meteo is out of quota.

Docs: https://api.met.no/weatherapi/locationforecast/2.0/documentation
Free and keyless, global, and limited per application (about 20 requests a second) rather
than per IP. It takes one location per request, so lookups snap to a coarser lattice and run
a few at a time. Steps are hourly for about 2.5 days, then 6-hourly.

It reports precipitation without splitting rain from snow, so precipitation at or below 1 °C
counts as snow, converted like Open-Meteo's snowfall (0.7 cm of snow per mm of water).
"""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from django.conf import settings
from django.core.cache import cache

from trips.domain.geo import LatLon
from trips.domain.weather import HourlySeries

from .base import ProviderError
from .http import get_json
from .openmeteo import _snap, choose_lattice

URL = "https://api.met.no/weatherapi/locationforecast/2.0/complete"
MS_TO_MPH = 2.236936
MM_TO_IN = 1 / 25.4
SNOW_CM_PER_MM = 0.7
SNOW_MAX_TEMP_C = 1.0


def parse_forecast(payload: dict, start: datetime | None = None, end: datetime | None = None) -> HourlySeries:
    lo = (start - timedelta(hours=6)).timestamp() if start else float("-inf")
    hi = (end + timedelta(hours=6)).timestamp() if end else float("inf")
    times, wind, gust, rain, snow = [], [], [], [], []
    for step in payload["properties"]["timeseries"]:
        t = datetime.fromisoformat(step["time"].replace("Z", "+00:00")).timestamp()
        if not lo <= t <= hi:
            continue
        data = step["data"]
        now = data["instant"]["details"]
        if "next_1_hours" in data:
            mm_hr = data["next_1_hours"]["details"].get("precipitation_amount", 0.0)
        elif "next_6_hours" in data:
            mm_hr = data["next_6_hours"]["details"].get("precipitation_amount", 0.0) / 6
        else:
            mm_hr = 0.0
        is_snow = now.get("air_temperature", 10.0) <= SNOW_MAX_TEMP_C
        speed = now.get("wind_speed", 0.0) * MS_TO_MPH
        times.append(t)
        wind.append(speed)
        gust.append(now.get("wind_speed_of_gust", 0.0) * MS_TO_MPH or speed)
        rain.append(0.0 if is_snow else mm_hr * MM_TO_IN)
        snow.append(mm_hr * SNOW_CM_PER_MM / 2.54 if is_snow else 0.0)
    if not times:
        raise ProviderError("MET Norway has no forecast for this time", status=502)
    return HourlySeries(times=times, wind_mph=wind, gust_mph=gust, rain_in_hr=rain, snow_in_hr=snow)


class MetNoWeather:
    def hourly(self, points: Sequence[LatLon], start: datetime, end: datetime) -> list[HourlySeries]:
        step = max(choose_lattice(points, settings.MET_NO_MAX_LOCATIONS), 0.25)
        snapped = [_snap(p, step) for p in points]
        unique = list(dict.fromkeys(snapped))
        keys = {p: f"metno:{p[0]:.3f}:{p[1]:.3f}" for p in unique}
        cached = cache.get_many(list(keys.values()))
        series = {p: cached[k] for p, k in keys.items() if k in cached}

        missing = [p for p in unique if p not in series]
        if missing:
            with ThreadPoolExecutor(max_workers=settings.MET_NO_WORKERS) as pool:
                fetched = list(pool.map(self._fetch, missing))
            # The whole forecast is cached parsed (a few KB), not raw, so any window reuses it.
            series.update((p, parse_forecast(raw)) for p, raw in zip(missing, fetched))
            cache.set_many({keys[p]: series[p] for p in missing}, timeout=settings.WEATHER_CACHE_SECONDS)
        return [series[p] for p in snapped]

    @staticmethod
    def _fetch(p: LatLon) -> dict:
        return get_json(URL, {"lat": f"{p[0]:.4f}", "lon": f"{p[1]:.4f}"}, service="MET Norway")
