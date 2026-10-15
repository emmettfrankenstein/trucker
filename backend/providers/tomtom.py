"""TomTom Routing (truck profile) and Search adapters.

Docs: https://developer.tomtom.com/routing-api/documentation/tomtom-maps/calculate-route
      https://developer.tomtom.com/search-api/documentation/search-service/fuzzy-search
"""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import quote

from django.conf import settings

from trips.domain.geo import LatLon

from .base import Place, ProviderError, RoutePlan
from .http import get_json

LB_TO_KG = 0.45359237
BASE = "https://api.tomtom.com"


def _key() -> str:
    key = settings.TOMTOM_API_KEY
    if not key:
        raise ProviderError("TOMTOM_API_KEY is not configured", status=503)
    return key


def _loc(p: LatLon) -> str:
    return f"{p[0]:.6f},{p[1]:.6f}"


def parse_routes(payload: dict, via: LatLon | None = None) -> list[RoutePlan]:
    plans = []
    for route in payload.get("routes", []):
        summary = route["summary"]
        points = [(pt["latitude"], pt["longitude"]) for leg in route["legs"] for pt in leg["points"]]
        anchors = [
            (float(ins["routeOffsetInMeters"]), float(ins["travelTimeInSeconds"]))
            for ins in route.get("guidance", {}).get("instructions", [])
            if "routeOffsetInMeters" in ins and "travelTimeInSeconds" in ins
        ]
        plans.append(
            RoutePlan(
                points=points,
                distance_m=float(summary["lengthInMeters"]),
                duration_s=float(summary["travelTimeInSeconds"]),
                time_anchors=anchors,
                traffic_delay_s=float(summary.get("trafficDelayInSeconds", 0)),
                via=via,
            )
        )
    return plans


class TomTomRouting:
    name = "tomtom"

    def routes(
        self,
        origin: LatLon,
        destination: LatLon,
        *,
        depart_at: datetime,
        load_lb: float,
        alternatives: int = 2,
        via: LatLon | None = None,
    ) -> list[RoutePlan]:
        stops = [origin, via, destination] if via else [origin, destination]
        path = ":".join(_loc(p) for p in stops)
        params = {
            "key": _key(),
            "travelMode": "truck",
            "vehicleCommercial": "true",
            "vehicleWeight": round(load_lb * LB_TO_KG),
            "routeType": "fastest",
            "traffic": "true",
            "instructionsType": "coded",
            "computeTravelTimeFor": "all",
        }
        if depart_at > datetime.now(UTC):
            params["departAt"] = depart_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        if alternatives and not via:  # TomTom only supports alternatives without waypoints
            params["maxAlternatives"] = alternatives
        payload = get_json(f"{BASE}/routing/1/calculateRoute/{path}/json", params, service="TomTom Routing")
        plans = parse_routes(payload, via=via)
        if not plans:
            raise ProviderError("No truck route found between these places", status=422)
        return plans


def parse_places(payload: dict) -> list[Place]:
    out = []
    for r in payload.get("results", []):
        addr = r.get("address", {})
        label = r.get("poi", {}).get("name")
        free = addr.get("freeformAddress") or addr.get("municipality") or ""
        label = f"{label}, {free}" if label and free else (label or free)
        pos = r.get("position", {})
        if label and "lat" in pos and "lon" in pos:
            out.append(Place(label=label, lat=pos["lat"], lon=pos["lon"]))
    return out


class TomTomGeocoding:
    def search(self, query: str, *, limit: int = 6) -> list[Place]:
        params = {
            "key": _key(),
            "typeahead": "true",
            "limit": limit,
            "countrySet": settings.GEOCODE_COUNTRIES,
            "idxSet": "Geo,PAD,Addr,Str,POI",
        }
        payload = get_json(f"{BASE}/search/2/search/{quote(query)}.json", params, service="TomTom Search")
        return parse_places(payload)
