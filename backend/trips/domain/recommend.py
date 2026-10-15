"""Route-level metrics and the recommendation ranking."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from .risk import RiskLevel


@dataclass(frozen=True)
class ScoredSpan:
    miles: float
    level: RiskLevel


@dataclass
class RouteMetrics:
    key: str
    duration_s: float
    distance_mi: float
    miles_by_level: dict[RiskLevel, float] = field(default_factory=dict)
    avg_risk: float = 0.0
    max_level: RiskLevel = RiskLevel.LOW

    @property
    def no_travel_miles(self) -> float:
        return self.miles_by_level.get(RiskLevel.NO_TRAVEL, 0.0)

    @property
    def severe_miles(self) -> float:
        return self.miles_by_level.get(RiskLevel.SEVERE, 0.0)

    @property
    def high_miles(self) -> float:
        return self.miles_by_level.get(RiskLevel.HIGH, 0.0)

    def sort_key(self) -> tuple[float, ...]:
        # The brief's order is: fewest Severe miles, fewest High miles, lowest average
        # risk, shortest time. No Travel is not named; it is worse than Severe, so it
        # goes first. Miles are rounded to 0.1 so float noise never decides a tie.
        return (
            round(self.no_travel_miles, 1),
            round(self.severe_miles, 1),
            round(self.high_miles, 1),
            round(self.avg_risk, 3),
            self.duration_s,
        )


def compute_metrics(key: str, duration_s: float, spans: Sequence[ScoredSpan]) -> RouteMetrics:
    by_level = {level: 0.0 for level in RiskLevel}
    total = 0.0
    weighted = 0.0
    for span in spans:
        by_level[span.level] += span.miles
        total += span.miles
        weighted += span.miles * int(span.level)
    return RouteMetrics(
        key=key,
        duration_s=duration_s,
        distance_mi=total,
        miles_by_level=by_level,
        avg_risk=weighted / total if total else 0.0,
        max_level=max((s.level for s in spans), default=RiskLevel.LOW),
    )


@dataclass(frozen=True)
class Recommendation:
    ranking: list[str]  # route keys, best first
    recommended: str
    safe: bool  # False when every route crosses No Travel weather
    explanation: str


def _fmt_minutes(seconds: float) -> str:
    minutes = round(abs(seconds) / 60)
    h, m = divmod(minutes, 60)
    return f"{h} h {m} min" if h else f"{m} min"


_CRITERIA = (
    ("no_travel_miles", "No Travel miles"),
    ("severe_miles", "Severe miles"),
    ("high_miles", "High-risk miles"),
    ("avg_risk", "average risk"),
)


def _why(best: RouteMetrics, other: RouteMetrics) -> str:
    """One clause saying which criterion beat ``other``, plus the time trade-off."""
    bk, ok = best.sort_key(), other.sort_key()
    delta = other.duration_s - best.duration_s
    for idx, (attr, label) in enumerate(_CRITERIA):
        if bk[idx] < ok[idx]:
            b, o = getattr(best, attr), getattr(other, attr)
            fmt = "{:.2f}" if attr == "avg_risk" else "{:.0f}"
            adjective = "lower" if attr == "avg_risk" else "fewer"
            clause = f"{adjective} {label} than Route {other.key} ({fmt.format(b)} vs {fmt.format(o)})"
            if delta < -60:
                clause += f", though {_fmt_minutes(delta)} longer"
            return clause
    return f"same weather risk as Route {other.key} and {_fmt_minutes(delta)} faster"


def recommend(metrics: Sequence[RouteMetrics]) -> Recommendation:
    if not metrics:
        raise ValueError("no routes to rank")
    ranked = sorted(metrics, key=lambda m: m.sort_key())
    best = ranked[0]
    safe = best.no_travel_miles == 0

    parts = [_why(best, other) for other in ranked[1:]]
    if not safe:
        explanation = (
            f"Every route crosses No Travel conditions. Route {best.key} has the least exposure "
            f"({best.no_travel_miles:.0f} mi). Consider a later departure."
        )
    elif parts:
        explanation = f"Route {best.key} is recommended: " + "; ".join(parts) + "."
    else:
        explanation = f"Route {best.key} is the only route available."
    return Recommendation(
        ranking=[m.key for m in ranked],
        recommended=best.key,
        safe=safe,
        explanation=explanation,
    )
