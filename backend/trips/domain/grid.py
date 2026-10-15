"""Grid of forecast cells covering the corridor around a trip's routes (for the heatmap)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .geo import LatLon, cumulative_miles, haversine_mi

STEPS_DEG = (0.1, 0.15, 0.2, 0.25, 0.35, 0.5, 0.75, 1.0, 1.5)


@dataclass(frozen=True)
class Grid:
    step_deg: float
    cells: list[LatLon]  # cell centres


def _thin(points: Sequence[LatLon], every_mi: float) -> list[LatLon]:
    out = [points[0]]
    for p in points[1:]:
        if haversine_mi(out[-1], p) >= every_mi:
            out.append(p)
    out.append(points[-1])
    return out


def _cells_for_step(spine: Sequence[LatLon], step: float, reach_mi: float) -> list[LatLon]:
    """Walk the spine and collect every cell whose centre is within ``reach_mi``."""
    found: set[tuple[int, int]] = set()
    for lat, lon in spine:
        dlat = reach_mi / 69.0
        dlon = reach_mi / (69.0 * max(math.cos(math.radians(lat)), 0.2))
        for i in range(math.floor((lat - dlat) / step), math.floor((lat + dlat) / step) + 1):
            for j in range(math.floor((lon - dlon) / step), math.floor((lon + dlon) / step) + 1):
                if (i, j) in found:
                    continue
                centre = ((i + 0.5) * step, (j + 0.5) * step)
                if haversine_mi(centre, (lat, lon)) <= reach_mi:
                    found.add((i, j))
    return [(round((i + 0.5) * step, 4), round((j + 0.5) * step, 4)) for i, j in sorted(found)]


def corridor_grid(routes: Sequence[Sequence[LatLon]], buffer_mi: float = 30.0, max_cells: int = 450) -> Grid:
    """Square cells covering everything within ``buffer_mi`` of any route.

    Picks the finest step that keeps the count under ``max_cells``, so a short trip gets
    a detailed grid and a cross-country trip stays light enough to animate smoothly.
    """
    routes = [r for r in routes if r]
    if not routes:
        raise ValueError("no route points")
    spine = [q for r in routes for q in _thin(r, 3.0)]

    # Rough corridor area tells us which step to try first, avoiding wasted passes.
    longest = max(cumulative_miles(r)[-1] for r in routes)
    est_area = (longest * 1.6 + 2 * buffer_mi) * 2 * buffer_mi
    start = next(
        (i for i, s in enumerate(STEPS_DEG) if est_area / (s * 69.0 * s * 55.0) <= max_cells * 1.3),
        len(STEPS_DEG) - 1,
    )
    cells: list[LatLon] = []
    for step in STEPS_DEG[start:]:
        cells = _cells_for_step(spine, step, buffer_mi + step * 69.0 * 0.5)
        if len(cells) <= max_cells:
            return Grid(step_deg=step, cells=cells)
    return Grid(step_deg=STEPS_DEG[-1], cells=cells[:max_cells])
