import pytest

from trips.domain.geo import (
    cumulative_miles,
    decode_polyline,
    encode_polyline,
    haversine_mi,
    interp,
    point_at_mile,
    simplify_by_distance,
)


def test_haversine_known_distance():
    # Chicago to Denver is about 920 miles great-circle.
    assert haversine_mi((41.8781, -87.6298), (39.7392, -104.9903)) == pytest.approx(920, abs=10)


def test_polyline_round_trip():
    pts = [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]
    encoded = encode_polyline(pts)
    assert encoded == "_p~iF~ps|U_ulLnnqC_mqNvxq`@"  # Google's documented example
    assert decode_polyline(encoded) == pts


def test_interp_clamps_and_interpolates():
    xs, ys = [0, 10, 20], [0, 100, 300]
    assert interp(-5, xs, ys) == 0
    assert interp(5, xs, ys) == 50
    assert interp(15, xs, ys) == 200
    assert interp(25, xs, ys) == 300


def test_point_at_mile_ends_and_middle():
    pts = [(0.0, 0.0), (0.0, 1.0)]
    cum = cumulative_miles(pts)
    assert point_at_mile(pts, cum, 0) == pts[0]
    assert point_at_mile(pts, cum, cum[-1] + 1) == pts[-1]
    mid = point_at_mile(pts, cum, cum[-1] / 2)
    assert mid[1] == pytest.approx(0.5)


def test_simplify_keeps_endpoints():
    pts = [(0.0, i * 0.0001) for i in range(100)]
    out = simplify_by_distance(pts, min_gap_mi=0.1)
    assert out[0] == pts[0] and out[-1] == pts[-1]
    assert len(out) < len(pts)
