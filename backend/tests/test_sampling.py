import itertools

import pytest

from trips.domain.geo import cumulative_miles
from trips.domain.sampling import sample_route, time_curve

# A straight east-west line along the equator: 1 degree ≈ 69.1 miles.
LINE = [(0.0, i * 0.1) for i in range(31)]  # ~207 miles


@pytest.mark.parametrize("interval", [10, 25, 50])
def test_checkpoint_spacing(interval):
    pts = sample_route(LINE, interval, total_seconds=3600 * 4)
    total = cumulative_miles(LINE)[-1]
    miles = [p.mile for p in pts]
    assert miles[0] == 0
    assert miles[-1] == pytest.approx(total)
    assert all(b - a == pytest.approx(interval) for a, b in itertools.pairwise(miles[:-1]))
    assert miles[-1] - miles[-2] <= interval + 1e-9


def test_spans_tile_the_route_exactly():
    pts = sample_route(LINE, 25, total_seconds=7200)
    assert pts[0].span_start_mi == 0
    assert pts[-1].span_end_mi == pytest.approx(pts[-1].mile)
    for a, b in itertools.pairwise(pts):
        assert a.span_end_mi == pytest.approx(b.span_start_mi)
    assert sum(p.span_mi for p in pts) == pytest.approx(pts[-1].mile)


def test_eta_uses_router_anchors_not_average_speed():
    total = cumulative_miles(LINE)[-1]
    # First half of the distance takes 3/4 of the time (city traffic), second half is fast.
    anchors = [(total / 2 * 1609.344, 3 * 3600)]
    pts = sample_route(LINE, 10, total_seconds=4 * 3600, anchors=anchors)
    half = min(pts, key=lambda p: abs(p.mile - total / 2))
    assert half.offset_s == pytest.approx(3 * 3600, rel=0.05)
    assert pts[-1].offset_s == pytest.approx(4 * 3600)
    assert all(a.offset_s <= b.offset_s for a, b in itertools.pairwise(pts))


def test_route_miles_rescales_geometry():
    geo_total = cumulative_miles(LINE)[-1]
    pts = sample_route(LINE, 50, total_seconds=3600, route_miles=geo_total * 1.1)
    assert pts[-1].mile == pytest.approx(geo_total * 1.1)
    assert (pts[-1].lat, pts[-1].lon) == LINE[-1]


def test_time_curve_ignores_non_monotonic_anchors():
    miles, secs = time_curve(100, 1000, anchors=[(80_000, 500), (40_000, 600), (200_000, 50)])
    assert miles == sorted(miles) and secs == sorted(secs)
    assert miles[-1] == 100 and secs[-1] == 1000


def test_short_route_has_origin_and_destination_only():
    pts = sample_route([(0.0, 0.0), (0.0, 0.05)], 25, total_seconds=600)
    assert [p.seq for p in pts] == [0, 1]


def test_invalid_input():
    with pytest.raises(ValueError):
        sample_route(LINE, 0, 100)
    with pytest.raises(ValueError):
        sample_route(LINE[:1], 10, 100)
