import pytest
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def fake_providers(settings):
    settings.PROVIDERS = {
        "routing": "tests.fakes.FakeRouting",
        "geocoding": "tests.fakes.FakeGeocoding",
        "weather": "tests.fakes.FakeWeather",
    }
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_CLASSES": (),
    }
    from tests.fakes import FakeRouting

    FakeRouting.alternatives_returned = 2
    FakeRouting.calls = []


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="driver", password="s3cure-pass-123")


@pytest.fixture
def auth_api(api, user):
    resp = api.post("/api/auth/token/", {"username": "driver", "password": "s3cure-pass-123"}, format="json")
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
    return api
