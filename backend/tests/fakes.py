"""Deterministic stand-ins for the external APIs, used by API tests and offline demos.

FakeRouting returns a straight fast route plus two arcs (north and south).
FakeWeather puts a wind storm north of ``STORM_LAT`` so the northern arc scores worst.
"""

from datetime import timedelta

from providers.base import Place, RoutePlan
from trips.domain.geo import METERS_PER_MILE, cumulative_miles
from trips.domain.weather import HourlySeries

STORM_LAT = 41.4


def _arc(o, d, bulge, n=60):
    pts = []
    for i in range(n + 1):
        t = i / n
        lat = o[0] + (d[0] - o[0]) * t + bulge * 4 * t * (1 - t)
        lon = o[1] + (d[1] - o[1]) * t
        pts.append((lat, lon))
    return pts


def _plan(points, mph, via=None):
    miles = cumulative_miles(points)[-1]
    duration = miles / mph * 3600
    return RoutePlan(
        points=points,
        distance_m=miles * METERS_PER_MILE,
        duration_s=duration,
        time_anchors=[(miles / 2 * METERS_PER_MILE, duration / 2)],
        via=via,
    )


class FakeRouting:
    name = "fake"
    alternatives_returned = 2
    calls = []

    def routes(self, origin, destination, *, depart_at, load_lb, alternatives=2, via=None):
        type(self).calls.append({"via": via, "load_lb": load_lb})
        if via:
            return [_plan(_arc(origin, destination, via[0] - (origin[0] + destination[0]) / 2), 50, via=via)]
        plans = [_plan(_arc(origin, destination, 0.0), 60)]
        if alternatives and self.alternatives_returned >= 1:
            plans.append(_plan(_arc(origin, destination, 0.8), 55))
        if alternatives and self.alternatives_returned >= 2:
            plans.append(_plan(_arc(origin, destination, -0.8), 50))
        return plans


class FakeGeocoding:
    def search(self, query, *, limit=6):
        return [Place(label=f"{query.title()}, IL", lat=41.88, lon=-87.63)]


class FakeWeather:
    def hourly(self, points, start, end):
        t0 = start.replace(minute=0, second=0, microsecond=0)
        hours = int((end - t0) / timedelta(hours=1)) + 2
        times = [(t0 + timedelta(hours=h)).timestamp() for h in range(hours)]
        out = []
        for lat, _lon in points:
            wind = 50.0 if lat > STORM_LAT else 10.0
            out.append(HourlySeries(times, [wind] * hours, [wind + 8] * hours, [0.0] * hours, [0.0] * hours))
        return out
