"""Hourly forecast series for one location, sampled at an arbitrary instant."""

from __future__ import annotations

from dataclasses import dataclass

from .geo import interp


@dataclass(frozen=True)
class WeatherSample:
    wind_mph: float
    gust_mph: float
    rain_in_hr: float
    snow_in_hr: float


@dataclass(frozen=True)
class HourlySeries:
    times: list[float]  # unix seconds, ascending, hourly
    wind_mph: list[float]
    gust_mph: list[float]
    rain_in_hr: list[float]
    snow_in_hr: list[float]

    def covers(self, t: float) -> bool:
        return bool(self.times) and self.times[0] <= t <= self.times[-1]

    def at(self, t: float) -> WeatherSample:
        """Linearly interpolate between the two forecast hours around ``t``."""
        return WeatherSample(
            wind_mph=interp(t, self.times, self.wind_mph),
            gust_mph=interp(t, self.times, self.gust_mph),
            rain_in_hr=interp(t, self.times, self.rain_in_hr),
            snow_in_hr=interp(t, self.times, self.snow_in_hr),
        )
