"""External service adapters, resolved from settings so tests can swap in fakes."""

from django.conf import settings
from django.utils.module_loading import import_string

from .base import GeocodingProvider, RoutingProvider, WeatherProvider


def routing() -> RoutingProvider:
    return import_string(settings.PROVIDERS["routing"])()


def geocoding() -> GeocodingProvider:
    return import_string(settings.PROVIDERS["geocoding"])()


def weather() -> WeatherProvider:
    return import_string(settings.PROVIDERS["weather"])()
