from trips.domain.alternatives import is_distinct, overlap_ratio, via_candidates
from trips.domain.geo import haversine_mi
from trips.domain.grid import corridor_grid

ROUTE = [(40.0, -100.0 + i * 0.05) for i in range(101)]  # ~265 mi east-west


def test_grid_cells_stay_within_corridor_and_cap():
    grid = corridor_grid([ROUTE], buffer_mi=30, max_cells=450)
    assert 0 < len(grid.cells) <= 450
    reach = 30 + grid.step_deg * 69 * 0.5
    assert all(min(haversine_mi(c, p) for p in ROUTE) <= reach + 1 for c in grid.cells)


def test_grid_coarsens_for_long_trips():
    short = corridor_grid([ROUTE[:20]])
    cross_country = corridor_grid([[(38.0, -122.0 + i * 0.5) for i in range(100)]])
    assert cross_country.step_deg > short.step_deg
    assert len(cross_country.cells) <= 450


def test_via_points_sit_either_side_of_route():
    vias = via_candidates(ROUTE[0], ROUTE[-1], ROUTE)
    assert len(vias) == 4
    lats = sorted(v[0] for v in vias)
    assert lats[0] < 40 < lats[-1]


def test_via_points_skipped_for_tiny_trips():
    assert via_candidates((40.0, -100.0), (40.0, -100.01), ROUTE) == []


def test_overlap_detection():
    shifted = [(lat + 0.5, lon) for lat, lon in ROUTE]  # ~35 mi north
    assert overlap_ratio(ROUTE, ROUTE) == 1.0
    assert overlap_ratio(shifted, ROUTE) == 0.0
    assert is_distinct(shifted, [ROUTE])
    assert not is_distinct(ROUTE, [ROUTE])
