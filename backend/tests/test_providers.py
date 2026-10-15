import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import respx
from django.core.cache import cache

from providers.base import ProviderError
from providers.fallback import FallbackWeather
from providers.metno import MetNoWeather, parse_forecast
from providers.nws import NwsWeather, parse_grid
from providers.openmeteo import OpenMeteoWeather, _window, choose_lattice, parse_location
from providers.tomtom import TomTomGeocoding, TomTomRouting, parse_places, parse_routes

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(autouse=True)
def _settings(settings):
    settings.TOMTOM_API_KEY = "test-key"
    settings.OPEN_METEO_API_KEY = ""
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    cache.clear()


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
    assert params["latitude"] == "41.000,42.000"
    assert params["wind_speed_unit"] == "mph"

    OpenMeteoWeather().hourly(pts, start, start + timedelta(hours=2))
    assert api.call_count == 1  # served from cache


def test_weather_rejects_trips_beyond_forecast_horizon():
    start = datetime.now(UTC) + timedelta(days=20)
    with pytest.raises(ProviderError):
        OpenMeteoWeather().hourly([(41, -88)], start, start + timedelta(hours=1))


def _hourly_response(request):
    lats = request.url.params["latitude"].split(",")
    t0 = int(datetime.fromisoformat(request.url.params["start_hour"]).replace(tzinfo=UTC).timestamp())
    return httpx.Response(200, json=[_om_item(t0, hours=60) for _ in lats])


def test_window_is_whole_days_of_at_least_49_hours():
    start = datetime(2026, 10, 16, 10, 30, tzinfo=UTC)
    s, e = _window(start, start + timedelta(hours=3))
    assert s == datetime(2026, 10, 16, 10, tzinfo=UTC)
    assert e - s == timedelta(days=3)
    s2, e2 = _window(start, start + timedelta(hours=48))
    assert (s2, e2) == (s, e)  # trip and its 0-48 h heatmap share one window (and cache)


def test_lattice_coarsens_for_long_trips():
    short = [(40.0, -100.0 + i * 0.15) for i in range(100)]
    long = [(40.0 + (i % 7) * 0.05, -125.0 + i * 0.03) for i in range(2000)]
    assert choose_lattice(short, 300) == 0.1
    assert choose_lattice(long, 300) > 0.1
    assert (
        len({(round(p[0] / choose_lattice(long, 300)), round(p[1] / choose_lattice(long, 300))) for p in long}) <= 300
    )


@respx.mock
def test_long_trip_stays_within_one_request_budget(settings):
    settings.OPEN_METEO_MAX_LOCATIONS_PER_REQUEST = 300
    api = respx.get("https://api.open-meteo.com/v1/forecast").mock(side_effect=_hourly_response)
    pts = [(45.0 + (i % 5) * 0.02, -125.0 + i * 0.05) for i in range(1300)]  # ~3,400 mi at 10 mi
    start = datetime.now(UTC) + timedelta(hours=1)
    series = OpenMeteoWeather().hourly(pts, start, start + timedelta(hours=60))
    assert len(series) == len(pts)
    sent = sum(len(c.request.url.params["latitude"].split(",")) for c in api.calls)
    assert sent <= 300


@respx.mock
def test_minute_budget_refuses_before_calling(settings):
    settings.OPEN_METEO_LOCATIONS_PER_MINUTE = 150
    api = respx.get("https://api.open-meteo.com/v1/forecast").mock(side_effect=_hourly_response)
    start = datetime.now(UTC) + timedelta(hours=1)
    OpenMeteoWeather().hourly([(40.0, -100.0 + i) for i in range(100)], start, start + timedelta(hours=2))
    with pytest.raises(ProviderError) as exc:
        OpenMeteoWeather().hourly([(41.0, -100.0 + i) for i in range(100)], start, start + timedelta(hours=2))
    assert exc.value.status == 503
    assert "usage limit" in str(exc.value)
    assert 0 < exc.value.retry_after <= 60
    assert api.call_count == 1
    # Cached locations cost nothing, so repeating the first trip still works.
    OpenMeteoWeather().hourly([(40.0, -100.0 + i) for i in range(100)], start, start + timedelta(hours=2))


@respx.mock
def test_upstream_429_becomes_a_friendly_503():
    respx.get("https://api.open-meteo.com/v1/forecast").mock(
        return_value=httpx.Response(429, json={"reason": "Minutely API request limit exceeded"})
    )
    start = datetime.now(UTC) + timedelta(hours=1)
    with pytest.raises(ProviderError) as exc:
        OpenMeteoWeather().hourly([(40.0, -100.0)], start, start + timedelta(hours=2))
    assert exc.value.status == 503
    assert "try again in about a minute" in str(exc.value)


@respx.mock
def test_api_key_uses_commercial_endpoint_without_budget(settings):
    settings.OPEN_METEO_API_KEY = "paid"
    settings.OPEN_METEO_LOCATIONS_PER_MINUTE = 1
    api = respx.get("https://customer-api.open-meteo.com/v1/forecast").mock(side_effect=_hourly_response)
    start = datetime.now(UTC) + timedelta(hours=1)
    OpenMeteoWeather().hourly([(40.0, -100.0 + i) for i in range(5)], start, start + timedelta(hours=2))
    assert api.calls.last.request.url.params["apikey"] == "paid"


@respx.mock
def test_hourly_quota_reports_when_it_resets():
    respx.get("https://api.open-meteo.com/v1/forecast").mock(
        return_value=httpx.Response(429, json={"error": True, "reason": "Hourly API request limit exceeded"})
    )
    start = datetime.now(UTC) + timedelta(hours=1)
    with pytest.raises(ProviderError) as exc:
        OpenMeteoWeather().hourly([(40.0, -100.0)], start, start + timedelta(hours=2))
    assert 0 < exc.value.retry_after <= 3600


@respx.mock
def test_hour_budget_refuses_before_calling(settings):
    settings.OPEN_METEO_LOCATIONS_PER_HOUR = 50
    api = respx.get("https://api.open-meteo.com/v1/forecast").mock(side_effect=_hourly_response)
    start = datetime.now(UTC) + timedelta(hours=1)
    with pytest.raises(ProviderError) as exc:
        OpenMeteoWeather().hourly([(40.0, -100.0 + i) for i in range(60)], start, start + timedelta(hours=2))
    assert exc.value.unavailable
    assert api.call_count == 0
    # The refused request is not counted, so a smaller one still fits.
    OpenMeteoWeather().hourly([(40.0, -100.0 + i) for i in range(40)], start, start + timedelta(hours=2))


def _met_payload(t0, temp=5.0, hourly=60, six_hourly=10):
    steps = []
    for i in range(hourly):
        steps.append(
            {
                "time": datetime.fromtimestamp(t0 + 3600 * i, UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "data": {
                    "instant": {"details": {"air_temperature": temp, "wind_speed": 10.0, "wind_speed_of_gust": 20.0}},
                    "next_1_hours": {"details": {"precipitation_amount": 2.54}},
                    "next_6_hours": {"details": {"precipitation_amount": 6.0}},
                },
            }
        )
    for j in range(six_hourly):
        steps.append(
            {
                "time": datetime.fromtimestamp(t0 + 3600 * (hourly + 6 * j), UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "data": {
                    "instant": {"details": {"air_temperature": temp, "wind_speed": 10.0}},
                    "next_6_hours": {"details": {"precipitation_amount": 15.24}},
                },
            }
        )
    return {"properties": {"meta": {"units": {"wind_speed": "m/s"}}, "timeseries": steps}}


def test_met_no_parses_units_six_hour_steps_and_snow():
    start = datetime(2026, 10, 16, tzinfo=UTC)
    t0 = int(start.timestamp())
    warm = parse_forecast(_met_payload(t0), start, start + timedelta(hours=120))
    assert warm.wind_mph[0] == pytest.approx(22.37, abs=0.01)
    assert warm.gust_mph[0] == pytest.approx(44.74, abs=0.01)
    assert warm.rain_in_hr[0] == pytest.approx(0.1)
    assert warm.snow_in_hr[0] == 0
    assert warm.rain_in_hr[-1] == pytest.approx(0.1)  # 6-hour total spread per hour
    assert warm.gust_mph[-1] == warm.wind_mph[-1]  # no gust reported: fall back to sustained
    cold = parse_forecast(_met_payload(t0, temp=-2.0), start, start + timedelta(hours=10))
    assert cold.rain_in_hr[0] == 0
    assert cold.snow_in_hr[0] == pytest.approx(0.7)  # 2.54 mm water -> 1.778 cm -> 0.7 in
    assert len(cold.times) < 30  # trimmed to the requested window


def _met_response(request):
    t0 = int(datetime.now(UTC).replace(minute=0, second=0, microsecond=0).timestamp())
    return httpx.Response(200, json=_met_payload(t0))


@respx.mock
def test_met_no_snaps_fetches_each_location_once_and_caches():
    api = respx.get("https://api.met.no/weatherapi/locationforecast/2.0/complete").mock(side_effect=_met_response)
    start = datetime.now(UTC) + timedelta(hours=1)
    pts = [(41.01, -88.0), (41.05, -88.02), (42.0, -87.0)]
    series = MetNoWeather().hourly(pts, start, start + timedelta(hours=10))
    assert len(series) == 3
    assert api.call_count == 2
    assert "trucker" in api.calls.last.request.headers["User-Agent"]
    MetNoWeather().hourly(pts, start, start + timedelta(hours=10))
    assert api.call_count == 2


OM_THEN_MET = ["providers.openmeteo.OpenMeteoWeather", "providers.metno.MetNoWeather"]


@respx.mock
def test_fallback_uses_met_no_when_open_meteo_is_out_of_quota(settings):
    settings.WEATHER_PROVIDER_CHAIN = OM_THEN_MET
    om = respx.get("https://api.open-meteo.com/v1/forecast").mock(
        return_value=httpx.Response(429, json={"error": True, "reason": "Daily API request limit exceeded"})
    )
    met = respx.get("https://api.met.no/weatherapi/locationforecast/2.0/complete").mock(side_effect=_met_response)
    start = datetime.now(UTC) + timedelta(hours=1)
    series = FallbackWeather().hourly([(32.8, -96.8)], start, start + timedelta(hours=10))
    assert series[0].wind_mph[0] > 0
    assert (om.call_count, met.call_count) == (1, 1)
    # Open-Meteo rests until its quota resets instead of being asked again on every trip.
    FallbackWeather().hourly([(33.8, -84.4)], start, start + timedelta(hours=10))
    assert (om.call_count, met.call_count) == (1, 2)


@respx.mock
def test_fallback_does_not_mask_bad_input(settings):
    settings.WEATHER_PROVIDER_CHAIN = OM_THEN_MET
    start = datetime.now(UTC) + timedelta(days=20)
    met = respx.get("https://api.met.no/weatherapi/locationforecast/2.0/complete").mock(side_effect=_met_response)
    with pytest.raises(ProviderError) as exc:
        FallbackWeather().hourly([(41, -88)], start, start + timedelta(hours=1))
    assert exc.value.status == 400
    assert met.call_count == 0


@respx.mock
def test_fallback_reports_the_first_error_when_every_source_fails(settings):
    settings.WEATHER_PROVIDER_CHAIN = OM_THEN_MET
    respx.get("https://api.open-meteo.com/v1/forecast").mock(return_value=httpx.Response(429, json={}))
    respx.get("https://api.met.no/weatherapi/locationforecast/2.0/complete").mock(return_value=httpx.Response(503))
    start = datetime.now(UTC) + timedelta(hours=1)
    with pytest.raises(ProviderError) as exc:
        FallbackWeather().hourly([(41, -88)], start, start + timedelta(hours=1))
    assert "Open-Meteo" in str(exc.value)


def _iso(t):
    return datetime.fromtimestamp(t, UTC).isoformat()


def _grid(t0, wind_kmh=40.0):
    return {
        "properties": {
            "windSpeed": {"uom": "wmoUnit:km_h-1", "values": [{"validTime": f"{_iso(t0)}/PT2H", "value": wind_kmh}]},
            "windGust": {"uom": "wmoUnit:km_h-1", "values": [{"validTime": f"{_iso(t0)}/PT1H", "value": 80.0}]},
            "quantitativePrecipitation": {
                "uom": "wmoUnit:mm",
                "values": [{"validTime": f"{_iso(t0)}/PT2H", "value": 10.16}],
            },
            "snowfallAmount": {"uom": "wmoUnit:mm", "values": [{"validTime": f"{_iso(t0)}/PT2H", "value": 25.4}]},
        }
    }


def test_nws_grid_expands_periods_converts_units_and_splits_snow():
    s = parse_grid(_grid(0)["properties"])
    assert s.times == [0.0, 3600.0]  # a PT2H value covers two hours
    assert s.wind_mph[1] == pytest.approx(24.85, abs=0.01)
    assert s.gust_mph == [pytest.approx(49.71, abs=0.01), s.wind_mph[1]]  # never below sustained
    assert s.snow_in_hr[0] == pytest.approx(0.5)  # 25.4 mm over 2 h
    # 5.08 mm/h of liquid, of which 1.27 mm/h is the snow's water at 10:1
    assert s.rain_in_hr[0] == pytest.approx((5.08 - 1.27) / 25.4)
    assert parse_grid({"windSpeed": {"values": []}}) is None


def _nws_routes(t0):
    respx.get(url__regex=r"https://api\.weather\.gov/points/4\d.*").mock(
        side_effect=lambda r: httpx.Response(
            200, json={"properties": {"forecastGridData": "https://api.weather.gov/gridpoints/LOT/1,1"}}
        )
    )
    respx.get(url__regex=r"https://api\.weather\.gov/points/5\d.*").mock(
        return_value=httpx.Response(404, json={"title": "Data Unavailable For Requested Point"})
    )
    return respx.get("https://api.weather.gov/gridpoints/LOT/1,1").mock(
        return_value=httpx.Response(200, json=_grid(t0))
    )


@respx.mock
def test_nws_shares_grid_cells_skips_points_outside_the_us_and_caches():
    start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    grid = _nws_routes(int(start.timestamp()))
    pts = [(41.8, -87.6), (41.9, -87.7), (55.0, -100.0)]
    series = NwsWeather().hourly(pts, start, start + timedelta(hours=2))
    assert series[0] is series[1]
    assert series[2] is None
    assert grid.call_count == 1
    assert respx.calls.call_count == 4
    assert respx.calls[0].request.url.path == "/points/41.8,-87.6"  # canonical, no trailing zeros
    NwsWeather().hourly(pts, start, start + timedelta(hours=2))
    assert respx.calls.call_count == 4  # points, outside-US marker and grid all cached


@respx.mock
def test_nws_grid_failure_leaves_points_for_the_next_source():
    respx.get(url__regex=r"https://api\.weather\.gov/points/.*").mock(
        return_value=httpx.Response(
            200, json={"properties": {"forecastGridData": "https://api.weather.gov/gridpoints/X/1,1"}}
        )
    )
    respx.get("https://api.weather.gov/gridpoints/X/1,1").mock(return_value=httpx.Response(400, json={}))
    start = datetime.now(UTC)
    assert NwsWeather().hourly([(41.8, -87.6)], start, start + timedelta(hours=2)) == [None]


@respx.mock
def test_default_chain_mixes_nws_in_the_us_with_met_no_elsewhere():
    start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    _nws_routes(int(start.timestamp()))
    met = respx.get("https://api.met.no/weatherapi/locationforecast/2.0/complete").mock(side_effect=_met_response)
    om = respx.get("https://api.open-meteo.com/v1/forecast").mock(side_effect=_hourly_response)
    series = FallbackWeather().hourly([(41.8, -87.6), (55.0, -100.0)], start, start + timedelta(hours=2))
    assert series[0].wind_mph[0] == pytest.approx(24.85, abs=0.01)  # NWS
    assert series[1].wind_mph[0] == pytest.approx(22.37, abs=0.01)  # MET Norway
    assert met.call_count == 1
    assert om.call_count == 0


@respx.mock
def test_open_meteo_is_the_last_resort():
    respx.get(url__regex=r"https://api\.weather\.gov/.*").mock(return_value=httpx.Response(503))
    respx.get("https://api.met.no/weatherapi/locationforecast/2.0/complete").mock(return_value=httpx.Response(429))
    om = respx.get("https://api.open-meteo.com/v1/forecast").mock(side_effect=_hourly_response)
    start = datetime.now(UTC) + timedelta(hours=1)
    series = FallbackWeather().hourly([(41.8, -87.6)], start, start + timedelta(hours=2))
    assert series[0] is not None
    assert om.call_count == 1
