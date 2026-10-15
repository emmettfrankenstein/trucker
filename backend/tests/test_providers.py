import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import respx

from providers.base import ProviderError
from providers.openmeteo import OpenMeteoWeather, parse_location
from providers.tomtom import TomTomGeocoding, TomTomRouting, parse_places, parse_routes

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(autouse=True)
def _settings(settings):
    settings.TOMTOM_API_KEY = "test-key"
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


def test_parse_routes_reads_geometry_summary_and_guidance_anchors():
    plans = parse_routes(load("tomtom_route.json"))
    assert len(plans) == 2
    first = plans[0]
    assert first.points[0] == (41.0, -88.0)
    assert first.distance_m == 160934 and first.duration_s == 7200
    assert first.traffic_delay_s == 120
    assert first.time_anchors[1] == (80000.0, 4500.0)
    assert plans[1].time_anchors == []  # guidance is optional


def test_parse_places_labels_pois_and_skips_unusable_results():
    places = parse_places(load("tomtom_search.json"))
    assert [p.label for p in places] == [
        "Chicago, IL",
        "Chicago Midway Airport, 5700 S Cicero Ave, Chicago, IL 60638",
    ]


@respx.mock
def test_routing_request_uses_truck_profile_and_weight_in_kg():
    route = respx.get(url__regex=r"https://api\.tomtom\.com/routing/1/calculateRoute/.*").mock(
        return_value=httpx.Response(200, json=load("tomtom_route.json"))
    )
    depart = datetime.now(UTC) + timedelta(hours=2)
    plans = TomTomRouting().routes((41, -88), (41, -86.1), depart_at=depart, load_lb=40_000)
    assert len(plans) == 2
    params = route.calls.last.request.url.params
    assert params["travelMode"] == "truck"
    assert params["vehicleWeight"] == "18144"
    assert params["maxAlternatives"] == "2"
    assert params["departAt"].endswith("Z")


@respx.mock
def test_routing_with_via_point_drops_alternatives():
    route = respx.get(url__regex=r".*calculateRoute/41\.000000,-88\.000000:41\.500000,-87\.000000:.*").mock(
        return_value=httpx.Response(200, json=load("tomtom_route.json"))
    )
    TomTomRouting().routes((41, -88), (41, -86.1), depart_at=datetime.now(UTC), load_lb=1, via=(41.5, -87.0))
    assert "maxAlternatives" not in route.calls.last.request.url.params


@respx.mock
def test_routing_errors_become_provider_errors():
    respx.get(url__regex=r".*calculateRoute.*").mock(
        return_value=httpx.Response(400, json={"detailedError": {"message": "Engine error"}})
    )
    with pytest.raises(ProviderError) as exc:
        TomTomRouting().routes((41, -88), (41, -86), depart_at=datetime.now(UTC), load_lb=1)
    assert exc.value.status == 400
    assert "Engine error" in str(exc.value)


def test_missing_key_is_reported(settings):
    settings.TOMTOM_API_KEY = ""
    with pytest.raises(ProviderError) as exc:
        TomTomGeocoding().search("chicago")
    assert exc.value.status == 503


def _om_item(t0, hours=4, wind=10.0, unit_snow="inch"):
    return {
        "hourly_units": {
            "wind_speed_10m": "mp/h",
            "wind_gusts_10m": "mp/h",
            "rain": "inch",
            "showers": "inch",
            "snowfall": unit_snow,
        },
        "hourly": {
            "time": [t0 + 3600 * i for i in range(hours)],
            "wind_speed_10m": [wind + i for i in range(hours)],
            "wind_gusts_10m": [wind + 10] * hours,
            "rain": [0.1] * hours,
            "showers": [0.05] * hours,
            "snowfall": [2.54 if unit_snow == "cm" else 1.0] * hours,
        },
    }


def test_parse_location_adds_showers_to_rain_and_converts_cm_snow():
    series = parse_location(_om_item(0, unit_snow="cm"))
    assert series.rain_in_hr[0] == pytest.approx(0.15)
    assert series.snow_in_hr[0] == pytest.approx(1.0)
    assert series.at(1800).wind_mph == pytest.approx(10.5)


@respx.mock
def test_weather_batches_locations_and_caches_them():
    start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    t0 = int(start.timestamp())
    api = respx.get("https://api.open-meteo.com/v1/forecast").mock(
        return_value=httpx.Response(200, json=[_om_item(t0), _om_item(t0, wind=40)])
    )
    pts = [(41.001, -88.0), (42.0, -87.0), (41.0, -88.001)]  # first and third round to the same cell
    series = OpenMeteoWeather().hourly(pts, start, start + timedelta(hours=2))
    assert len(series) == 3
    assert series[0] is series[2]
    assert series[1].wind_mph[0] == 40
    params = api.calls.last.request.url.params
    assert params["latitude"] == "41.00,42.00"
    assert params["wind_speed_unit"] == "mph"

    OpenMeteoWeather().hourly(pts, start, start + timedelta(hours=2))
    assert api.call_count == 1  # served from cache


def test_weather_rejects_trips_beyond_forecast_horizon():
    start = datetime.now(UTC) + timedelta(days=20)
    with pytest.raises(ProviderError):
        OpenMeteoWeather().hourly([(41, -88)], start, start + timedelta(hours=1))
