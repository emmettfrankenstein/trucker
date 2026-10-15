"""Weather risk classification for a single checkpoint.

The assignment's table has touching ranges (e.g. rain 0.25 appears in both
Moderate and High). We resolve every boundary explicitly with half-open
intervals so each value maps to exactly one level:

    Wind (mph):    Low < 25 <= Moderate < 35 <= High < 45 <= Severe < 55 <= No Travel
    Rain (in/hr):  Low < 0.10 <= Moderate < 0.25 <= High < 0.50 <= Severe <= 1.00 < No Travel
    Snow (in/hr):  Low < 0.5  <= Moderate < 1.0  <= High < 2.0  <= Severe <= 3.0  < No Travel

The table is data, not if-chains, so thresholds can be tuned in one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class RiskLevel(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()


@dataclass(frozen=True)
class Band:
    """Lower bound at which a level starts and whether that bound is inclusive."""

    level: RiskLevel
    threshold: float
    inclusive: bool = True  # value >= threshold (True) or value > threshold (False)

    def matches(self, value: float) -> bool:
        return value >= self.threshold if self.inclusive else value > self.threshold


# Bands are checked from most to least severe; the first match wins.
RISK_TABLE: dict[str, tuple[Band, ...]] = {
    "wind": (
        Band(RiskLevel.NO_TRAVEL, 55),
        Band(RiskLevel.SEVERE, 45),
        Band(RiskLevel.HIGH, 35),
        Band(RiskLevel.MODERATE, 25),
    ),
    "rain": (
        Band(RiskLevel.NO_TRAVEL, 1.00, inclusive=False),
        Band(RiskLevel.SEVERE, 0.50),
        Band(RiskLevel.HIGH, 0.25),
        Band(RiskLevel.MODERATE, 0.10),
    ),
    "snow": (
        Band(RiskLevel.NO_TRAVEL, 3.0, inclusive=False),
        Band(RiskLevel.SEVERE, 2.0),
        Band(RiskLevel.HIGH, 1.0),
        Band(RiskLevel.MODERATE, 0.5),
    ),
}

UNITS = {"wind": "mph", "rain": "in/hr", "snow": "in/hr"}

# Load rules: (min wind mph, max wind mph exclusive, load strictly above lb, resulting level)
LOAD_RULES: tuple[tuple[float, float, float, RiskLevel], ...] = (
    (45, 55, 30_000, RiskLevel.NO_TRAVEL),
    (35, 45, 40_000, RiskLevel.SEVERE),
)


def classify_value(condition: str, value: float) -> RiskLevel:
    for band in RISK_TABLE[condition]:
        if band.matches(value):
            return band.level
    return RiskLevel.LOW


@dataclass(frozen=True)
class RiskAssessment:
    level: RiskLevel
    reasons: list[str] = field(default_factory=list)
    by_condition: dict[str, RiskLevel] = field(default_factory=dict)


def _fmt(value: float, condition: str) -> str:
    if condition == "wind":
        return f"{value:.0f} {UNITS[condition]}"
    return f"{value:.2f} {UNITS[condition]}"


def assess(*, wind_mph: float, rain_in_hr: float, snow_in_hr: float, load_lb: float) -> RiskAssessment:
    """Overall checkpoint risk: the worst condition after applying load rules."""
    values = {"wind": wind_mph, "rain": rain_in_hr, "snow": snow_in_hr}
    by_condition = {c: classify_value(c, v) for c, v in values.items()}
    reasons: dict[str, str] = {}

    for low, high, load_above, escalated in LOAD_RULES:
        if low <= wind_mph < high and load_lb > load_above and escalated > by_condition["wind"]:
            by_condition["wind"] = escalated
            reasons["wind"] = (
                f"Wind {_fmt(wind_mph, 'wind')} with {load_lb:,.0f} lb load "
                f"(> {load_above:,.0f} lb) → {escalated.label}"
            )
            break

    for condition, cond_level in by_condition.items():
        if cond_level > RiskLevel.LOW and condition not in reasons:
            reasons[condition] = f"{condition.title()} {_fmt(values[condition], condition)} → {cond_level.label}"

    ordered = sorted(reasons, key=lambda c: by_condition[c], reverse=True)
    return RiskAssessment(
        level=max(by_condition.values()),
        reasons=[reasons[c] for c in ordered],
        by_condition=by_condition,
    )
