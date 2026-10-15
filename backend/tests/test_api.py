import itertools
from datetime import timedelta

import pytest
from django.utils import timezone

from trips.models import Checkpoint, Trip

pytestmark = pytest.mark.django_db


def plan_body(**overrides):
    body = {
        "origin": {"label": "Des Moines, IA", "lat": 41.0, "lon": -93.6},
        "destination": {"label": "Chicago, IL", "lat": 41.0, "lon": -87.6},
        "departure_at": (timezone.now() + timedelta(hours=3)).isoformat(),
        "load_weight_lb": 36_000,
        "sample_interval_mi": 25,
    }
    body.update(overrides)
    return body


def test_plan_trip_returns_three_scored_routes_and_avoids_the_storm(api):
    resp = api.post("/api/trips/", plan_body(), format="json")
    assert resp.status_code == 201, resp.data
    data = resp.data
    assert [r["label"] for r in data["routes"]] == ["A", "B", "C"]

    by_label = {r["label"]: r for r in data["routes"]}
    # Route B arcs north into 50 mph wind; with 36,000 lb that is No Travel.
    assert by_label["B"]["max_level_label"] == "No Travel"
    assert by_label["B"]["rank"] == 3
    # A is straight and fastest with calm weather, so it wins.
    assert data["recommendation"]["route"] == "A"
    assert data["recommendation"]["safe"] is True
    assert by_label["A"]["is_recommended"]

    cps = by_label["A"]["checkpoints"]
    assert cps[0]["mile"] == 0
    assert all(b["mile"] - a["mile"] <= 25.01 for a, b in itertools.pairwise(cps))
    assert cps[-1]["eta"] > cps[0]["eta"]
    miles = sum(by_label["A"]["miles_by_level"].values())
    assert miles == pytest.approx(by_label["A"]["distance_mi"], rel=0.01)


def test_heavier_load_changes_the_risk(api):
    light = api.post("/api/trips/", plan_body(load_weight_lb=20_000), format="json").data
    heavy = api.post("/api/trips/", plan_body(load_weight_lb=36_000), format="json").data
    b_light = next(r for r in light["routes"] if r["label"] == "B")
    b_heavy = next(r for r in heavy["routes"] if r["label"] == "B")
    assert b_light["max_level_label"] == "Severe"
    assert b_heavy["max_level_label"] == "No Travel"


def test_missing_alternatives_are_filled_with_via_routes(api):
    from tests.fakes import FakeRouting

    FakeRouting.alternatives_returned = 0
    resp = api.post("/api/trips/", plan_body(), format="json")
    assert resp.status_code == 201
    assert len(resp.data["routes"]) == 3
    assert any(c["via"] for c in FakeRouting.calls)


def test_interval_controls_checkpoint_count(api):
    ten = api.post("/api/trips/", plan_body(sample_interval_mi=10), format="json").data
    fifty = api.post("/api/trips/", plan_body(sample_interval_mi=50), format="json").data
    assert len(ten["routes"][0]["checkpoints"]) > 2 * len(fifty["routes"][0]["checkpoints"])


@pytest.mark.parametrize(
    "overrides, field",
    [
        ({"load_weight_lb": 0}, "load_weight_lb"),
        ({"sample_interval_mi": 30}, "sample_interval_mi"),
        ({"departure_at": "2020-01-01T00:00:00Z"}, "departure_at"),
        ({"origin": {"label": "x", "lat": 120, "lon": 0}}, "origin"),
    ],
)
def test_plan_validation_errors_use_the_error_envelope(api, overrides, field):
    resp = api.post("/api/trips/", plan_body(**overrides), format="json")
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "invalid"
    assert field in resp.data["error"]["details"]


def test_same_origin_and_destination_rejected(api):
    place = {"label": "A", "lat": 41.0, "lon": -87.0}
    resp = api.post("/api/trips/", plan_body(origin=place, destination=place), format="json")
    assert resp.status_code == 400


def test_anonymous_trip_is_viewable_by_id_but_not_listed(api):
    trip_id = api.post("/api/trips/", plan_body(), format="json").data["id"]
    assert api.get(f"/api/trips/{trip_id}/").status_code == 200
    assert api.get("/api/trips/").status_code == 401


def test_signed_in_user_gets_history_and_privacy(auth_api, api, django_user_model):
    trip_id = auth_api.post("/api/trips/", plan_body(), format="json").data["id"]
    history = auth_api.get("/api/trips/").data
    assert [t["id"] for t in history] == [trip_id]

    other = django_user_model.objects.create_user(username="other", password="an0ther-pass-123")
    from rest_framework.test import APIClient

    stranger = APIClient()
    stranger.force_authenticate(other)
    assert stranger.get(f"/api/trips/{trip_id}/").status_code == 404
    assert stranger.delete(f"/api/trips/{trip_id}/").status_code == 404

    assert auth_api.delete(f"/api/trips/{trip_id}/").status_code == 204
    assert not Trip.objects.filter(pk=trip_id).exists()
    assert not Checkpoint.objects.exists()


def test_trip_detail_query_count_is_constant(api, django_assert_max_num_queries):
    trip_id = api.post("/api/trips/", plan_body(sample_interval_mi=10), format="json").data["id"]
    with django_assert_max_num_queries(3):  # trip + routes + checkpoints, no N+1
        api.get(f"/api/trips/{trip_id}/")


def test_heatmap_has_49_hourly_frames_and_is_stored(api):
    trip_id = api.post("/api/trips/", plan_body(), format="json").data["id"]
    resp = api.get(f"/api/trips/{trip_id}/heatmap/")
    assert resp.status_code == 200
    hm = resp.data
    assert hm["hours"] == 48
    n = len(hm["cells"])
    assert 0 < n <= 250
    for metric in ("risk", "wind", "rain", "snow"):
        assert len(hm["frames"][metric]) == 49
        assert all(len(row) == n for row in hm["frames"][metric])
    assert set(hm["frames"]["risk"][0]) <= {0, 4}  # calm or storm (50 mph + 36k lb)
    assert Trip.objects.get(pk=trip_id).heatmap is not None


def test_geocode_proxy(api):
    assert api.get("/api/geocode/?q=ch").data == []
    resp = api.get("/api/geocode/?q=chicago")
    assert resp.data[0]["label"] == "Chicago, IL"


def test_unknown_trip_404(api):
    resp = api.get("/api/trips/00000000-0000-0000-0000-000000000000/")
    assert resp.status_code == 404
    assert resp.data["error"]["code"] == "not_found"


def test_health_and_schema(api):
    assert api.get("/api/health/").data == {"status": "ok"}
    assert api.get("/api/schema/").status_code == 200
