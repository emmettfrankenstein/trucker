import pytest

from trips.domain.recommend import ScoredSpan, compute_metrics, recommend
from trips.domain.risk import RiskLevel

L, M, H, S, N = RiskLevel


def route(key, duration_s, *spans):
    return compute_metrics(key, duration_s, [ScoredSpan(miles, level) for miles, level in spans])


def test_metrics_sum_and_weighted_average():
    m = route("A", 3600, (50, L), (30, M), (20, S))
    assert m.distance_mi == 100
    assert m.miles_by_level[S] == 20
    assert m.avg_risk == pytest.approx((30 * 1 + 20 * 3) / 100)
    assert m.max_level is S


def test_fewest_severe_miles_wins_over_speed():
    a = route("A", 3600, (90, L), (10, S))
    b = route("B", 7200, (100, H))
    assert recommend([a, b]).recommended == "B"


def test_then_fewest_high_miles():
    a = route("A", 3600, (80, L), (20, H))
    b = route("B", 7200, (50, M), (50, M))
    assert recommend([a, b]).recommended == "B"


def test_then_lowest_average_risk():
    a = route("A", 3600, (50, M), (50, M))
    b = route("B", 7200, (80, L), (20, M))
    assert recommend([a, b]).recommended == "B"


def test_then_shortest_time():
    a = route("A", 7200, (100, L))
    b = route("B", 3600, (100, L))
    rec = recommend([a, b])
    assert rec.recommended == "B"
    assert "1 h 0 min faster" in rec.explanation


def test_no_travel_ranks_worse_than_severe():
    a = route("A", 3600, (99, L), (1, N))
    b = route("B", 3600, (50, S), (50, L))
    assert recommend([a, b]).ranking == ["B", "A"]


def test_all_routes_no_travel_is_flagged_unsafe():
    a = route("A", 3600, (90, L), (10, N))
    b = route("B", 3600, (95, L), (5, N))
    rec = recommend([a, b])
    assert rec.recommended == "B"
    assert rec.safe is False
    assert "later departure" in rec.explanation


def test_explanation_names_the_deciding_criterion():
    a = route("A", 3600, (90, L), (10, S))
    b = route("B", 4000, (100, L))
    assert "Severe miles: 0 vs 10 on Route A" in recommend([a, b]).explanation


def test_requires_routes():
    with pytest.raises(ValueError):
        recommend([])
