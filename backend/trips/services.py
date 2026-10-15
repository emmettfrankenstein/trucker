"""Trip planning use-cases. Views stay thin; everything that talks to providers or
assembles domain results lives here."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import transaction

import providers
from providers.base import Place, ProviderError, RoutePlan
from trips.domain import alternatives as alt
from trips.domain.geo import METERS_PER_MILE, LatLon, decode_polyline, encode_polyline, simplify_by_distance
from trips.domain.grid import corridor_grid
from trips.domain.recommend import RouteMetrics, ScoredSpan, compute_metrics, recommend
from trips.domain.risk import RiskLevel, assess
from trips.domain.sampling import SampledPoint, sample_route
from trips.domain.weather import HourlySeries

from .models import Checkpoint, Route, Trip

logger = logging.getLogger(__name__)

ROUTE_LABELS = "ABC"
TARGET_ROUTES = 3


def _wind_for_risk(sustained: float, gust: float) -> float:
    return gust if settings.RISK_WIND_FIELD == "gust" else sustained


# --- Geocoding --------------------------------------------------------------------------


def search_places(query: str) -> list[Place]:
    key = f"geo:{query.strip().lower()}"
    hit = cache.get(key)
    if hit is not None:
        return hit
    places = providers.geocoding().search(query)
    cache.set(key, places, timeout=settings.GEOCODE_CACHE_SECONDS)
    return places


# --- Routing ----------------------------------------------------------------------------


def fetch_routes(origin: LatLon, destination: LatLon, depart_at: datetime, load_lb: float) -> list[RoutePlan]:
    """Up to three distinct truck routes: the router's own alternatives first, then
    forced detours through side via-points if it returned fewer than three."""
    router = providers.routing()
    plans = router.routes(origin, destination, depart_at=depart_at, load_lb=load_lb, alternatives=2)
    plans = plans[:TARGET_ROUTES]
    if len(plans) >= TARGET_ROUTES:
        return plans

    vias = alt.via_candidates(origin, destination, plans[0].points)

    def try_via(via: LatLon) -> RoutePlan | None:
        try:
            return router.routes(origin, destination, depart_at=depart_at, load_lb=load_lb, alternatives=0, via=via)[0]
        except ProviderError as exc:  # an unroutable via-point is expected now and then
            logger.info("via-point %s rejected: %s", via, exc)
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        candidates = list(pool.map(try_via, vias))
    for cand in candidates:
        if len(plans) >= TARGET_ROUTES:
            break
        # A detour more than 60% longer than the fastest route is not a sensible option.
        if (
            cand
            and cand.duration_s <= plans[0].duration_s * 1.6
            and alt.is_distinct(cand.points, [p.points for p in plans])
        ):
            plans.append(cand)
    return plans


# --- Scoring ----------------------------------------------------------------------------


@dataclass
class ScoredCheckpoint:
    sample: SampledPoint
    eta: datetime
    wind_mph: float
    gust_mph: float
    rain_in_hr: float
    snow_in_hr: float
    level: RiskLevel
    reasons: list[str]


@dataclass
class ScoredRoute:
    label: str
    plan: RoutePlan
    checkpoints: list[ScoredCheckpoint]
    metrics: RouteMetrics


def score_routes(plans: list[RoutePlan], depart_at: datetime, load_lb: float, interval_mi: int) -> list[ScoredRoute]:
    samples = [
        sample_route(
            p.points,
            interval_mi,
            p.duration_s,
            anchors=p.time_anchors,
            route_miles=p.distance_m / METERS_PER_MILE,
        )
        for p in plans
    ]
    flat = [(s.lat, s.lon) for route in samples for s in route]
    latest = depart_at + timedelta(seconds=max(p.duration_s for p in plans))
    series = providers.weather().hourly(flat, depart_at, latest)

    out, k = [], 0
    for label, plan, route_samples in zip(ROUTE_LABELS, plans, samples):
        checkpoints, spans = [], []
        for s in route_samples:
            hs: HourlySeries = series[k]
            k += 1
            eta = depart_at + timedelta(seconds=s.offset_s)
            w = hs.at(eta.timestamp())
            risk = assess(
                wind_mph=_wind_for_risk(w.wind_mph, w.gust_mph),
                rain_in_hr=w.rain_in_hr,
                snow_in_hr=w.snow_in_hr,
                load_lb=load_lb,
            )
            checkpoints.append(
                ScoredCheckpoint(s, eta, w.wind_mph, w.gust_mph, w.rain_in_hr, w.snow_in_hr, risk.level, risk.reasons)
            )
            spans.append(ScoredSpan(miles=s.span_mi, level=risk.level))
        out.append(ScoredRoute(label, plan, checkpoints, compute_metrics(label, plan.duration_s, spans)))
    return out


def _summary(m: RouteMetrics) -> str:
    risky = [
        f"{m.miles_by_level[lvl]:.0f} mi {lvl.label}"
        for lvl in (RiskLevel.NO_TRAVEL, RiskLevel.SEVERE, RiskLevel.HIGH, RiskLevel.MODERATE)
        if m.miles_by_level[lvl] >= 0.5
    ]
    return ", ".join(risky) if risky else "Low risk the whole way"


# --- Use-case: plan a trip -------------------------------------------------------------


def plan_trip(
    *, user, origin: Place, destination: Place, departure_at: datetime, load_weight_lb: int, sample_interval_mi: int
) -> Trip:
    o, d = (origin.lat, origin.lon), (destination.lat, destination.lon)
    plans = fetch_routes(o, d, departure_at, load_weight_lb)
    scored = score_routes(plans, departure_at, load_weight_lb, sample_interval_mi)
    rec = recommend([r.metrics for r in scored])
    rank = {key: i + 1 for i, key in enumerate(rec.ranking)}

    with transaction.atomic():
        trip = Trip.objects.create(
            user=user if user and user.is_authenticated else None,
            origin_label=origin.label,
            origin_lat=origin.lat,
            origin_lon=origin.lon,
            destination_label=destination.label,
            destination_lat=destination.lat,
            destination_lon=destination.lon,
            departure_at=departure_at,
            load_weight_lb=load_weight_lb,
            sample_interval_mi=sample_interval_mi,
            routing_provider=providers.routing().name,
            recommendation_safe=rec.safe,
            recommendation_explanation=rec.explanation,
        )
        routes = Route.objects.bulk_create(
            [
                Route(
                    trip=trip,
                    label=r.label,
                    rank=rank[r.label],
                    is_recommended=r.label == rec.recommended,
                    distance_mi=r.plan.distance_m / METERS_PER_MILE,
                    duration_s=round(r.plan.duration_s),
                    traffic_delay_s=round(r.plan.traffic_delay_s),
                    geometry=encode_polyline(simplify_by_distance(r.plan.points)),
                    miles_by_level={lvl.name: round(r.metrics.miles_by_level[lvl], 2) for lvl in RiskLevel},
                    avg_risk=round(r.metrics.avg_risk, 4),
                    max_level=int(r.metrics.max_level),
                    summary=_summary(r.metrics),
                )
                for r in scored
            ]
        )
        Checkpoint.objects.bulk_create(
            [
                Checkpoint(
                    route=route,
                    seq=c.sample.seq,
                    lat=c.sample.lat,
                    lon=c.sample.lon,
                    mile=round(c.sample.mile, 2),
                    span_start_mi=round(c.sample.span_start_mi, 2),
                    span_end_mi=round(c.sample.span_end_mi, 2),
                    eta=c.eta,
                    wind_mph=round(c.wind_mph, 1),
                    gust_mph=round(c.gust_mph, 1),
                    rain_in_hr=round(c.rain_in_hr, 3),
                    snow_in_hr=round(c.snow_in_hr, 3),
                    risk_level=int(c.level),
                    reasons=c.reasons,
                )
                for route, r in zip(routes, scored)
                for c in r.checkpoints
            ]
        )
    return trip


# --- Use-case: corridor heatmap ---------------------------------------------------------


def build_heatmap(trip: Trip) -> dict:
    """Hourly frames (0..48 h from departure) for a grid covering the trip corridor.

    Columnar arrays keep the payload small; the client indexes ``frames[metric][hour][cell]``
    so scrubbing the slider never touches the network.
    """
    if trip.heatmap:
        return trip.heatmap
    routes = [decode_polyline(r.geometry) for r in trip.routes.all()]
    grid = corridor_grid(routes, buffer_mi=settings.HEATMAP_BUFFER_MI, max_cells=settings.HEATMAP_MAX_CELLS)
    # Frame 0 is the departure instant itself, so "+N h" on the slider means N hours after
    # the truck leaves; values between forecast hours are interpolated.
    start = trip.departure_at.astimezone(UTC).replace(second=0, microsecond=0)
    hours = settings.HEATMAP_HOURS
    series = providers.weather().hourly(grid.cells, start, start + timedelta(hours=hours))

    risk, wind, rain, snow = [], [], [], []
    for h in range(hours + 1):
        t = (start + timedelta(hours=h)).timestamp()
        r_row, w_row, p_row, s_row = [], [], [], []
        for hs in series:
            w = hs.at(t)
            level = assess(
                wind_mph=_wind_for_risk(w.wind_mph, w.gust_mph),
                rain_in_hr=w.rain_in_hr,
                snow_in_hr=w.snow_in_hr,
                load_lb=trip.load_weight_lb,
            ).level
            r_row.append(int(level))
            w_row.append(round(w.wind_mph))
            p_row.append(round(w.rain_in_hr, 2))
            s_row.append(round(w.snow_in_hr, 2))
        risk.append(r_row)
        wind.append(w_row)
        rain.append(p_row)
        snow.append(s_row)

    payload = {
        "start": start.isoformat().replace("+00:00", "Z"),
        "hours": hours,
        "step_deg": grid.step_deg,
        "cells": [[lat, lon] for lat, lon in grid.cells],
        "frames": {"risk": risk, "wind": wind, "rain": rain, "snow": snow},
    }
    Trip.objects.filter(pk=trip.pk).update(heatmap=payload)
    trip.heatmap = payload
    return payload
