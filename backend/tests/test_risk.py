import pytest

from trips.domain.risk import RiskLevel, assess, classify_value

L, M, H, S, N = RiskLevel


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, L),
        (24.9, L),
        (25, M),
        (34.9, M),
        (35, H),
        (44.9, H),
        (45, S),
        (54.9, S),
        (55, N),
        (80, N),
    ],
)
def test_wind_boundaries(value, expected):
    assert classify_value("wind", value) is expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, L),
        (0.099, L),
        (0.10, M),
        (0.249, M),
        (0.25, H),
        (0.499, H),
        (0.50, S),
        (1.00, S),
        (1.001, N),
        (2.0, N),
    ],
)
def test_rain_boundaries(value, expected):
    assert classify_value("rain", value) is expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, L),
        (0.49, L),
        (0.5, M),
        (0.99, M),
        (1.0, H),
        (1.99, H),
        (2.0, S),
        (3.0, S),
        (3.01, N),
    ],
)
def test_snow_boundaries(value, expected):
    assert classify_value("snow", value) is expected


def _wind(wind, load):
    return assess(wind_mph=wind, rain_in_hr=0, snow_in_hr=0, load_lb=load)


@pytest.mark.parametrize("load", [1, 10_000, 30_000, 40_000, 80_000])
def test_55_mph_is_no_travel_for_any_load(load):
    assert _wind(55, load).level is N


@pytest.mark.parametrize(
    "wind, load, expected",
    [
        (45, 30_000, S),  # rule needs strictly more than 30,000 lb
        (45, 30_001, N),
        (54.9, 30_001, N),
        (44.9, 30_001, H),  # below the 45 mph band, the 30k rule does not apply
        (35, 40_000, H),  # strictly more than 40,000 lb
        (35, 40_001, S),
        (44.9, 40_001, S),
        (34.9, 80_000, M),  # below 35 mph no load rule applies
        (50, 45_000, N),  # 45-54 band with >30k wins over the 35-44 rule
    ],
)
def test_load_rules(wind, load, expected):
    assert _wind(wind, load).level is expected


def test_load_rule_explains_itself():
    result = _wind(47, 36_000)
    assert result.level is N
    assert result.reasons == ["Wind 47 mph with 36,000 lb load (> 30,000 lb) → No Travel"]


def test_overall_level_is_worst_condition_and_reasons_are_sorted():
    result = assess(wind_mph=26, rain_in_hr=0.3, snow_in_hr=2.5, load_lb=20_000)
    assert result.level is S
    assert result.by_condition == {"wind": M, "rain": H, "snow": S}
    assert [r.split()[0] for r in result.reasons] == ["Snow", "Rain", "Wind"]


def test_calm_weather_has_no_reasons():
    result = assess(wind_mph=5, rain_in_hr=0, snow_in_hr=0, load_lb=80_000)
    assert result.level is L
    assert result.reasons == []
