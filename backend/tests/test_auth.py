import pytest

pytestmark = pytest.mark.django_db


def test_register_returns_tokens_and_me_works(api):
    resp = api.post(
        "/api/auth/register/",
        {"username": "newdriver", "email": "d@example.com", "password": "Long-enough-pass-1"},
        format="json",
    )
    assert resp.status_code == 201
    assert {"access", "refresh", "user"} <= resp.data.keys()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
    assert api.get("/api/auth/me/").data["username"] == "newdriver"


def test_register_rejects_weak_password_and_duplicates(api, user):
    weak = api.post("/api/auth/register/", {"username": "x1", "password": "123"}, format="json")
    assert weak.status_code == 400
    dup = api.post("/api/auth/register/", {"username": "DRIVER", "password": "Long-enough-pass-1"}, format="json")
    assert "username" in dup.data["error"]["details"]


def test_refresh_rotation_and_logout_blacklists(api, user):
    tokens = api.post("/api/auth/token/", {"username": "driver", "password": "s3cure-pass-123"}, format="json").data
    rotated = api.post("/api/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
    assert rotated.status_code == 200
    # The old refresh token was blacklisted on rotation.
    assert api.post("/api/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json").status_code == 401

    api.credentials(HTTP_AUTHORIZATION=f"Bearer {rotated.data['access']}")
    assert api.post("/api/auth/logout/", {"refresh": rotated.data["refresh"]}, format="json").status_code == 205
    assert api.post("/api/auth/token/refresh/", {"refresh": rotated.data["refresh"]}, format="json").status_code == 401


def test_me_requires_auth(api):
    assert api.get("/api/auth/me/").status_code == 401
