from app.service.google_oauth import GoogleProfile
from test.conftest import auth_headers


def _mock_google_profile(monkeypatch, *, google_id="g-123", email="orok@gmail.com", full_name="Orok Dev"):
    """Swaps out the real Google token verification for a fake profile, so
    tests never need a real Google ID token. AuthService imported
    verify_google_id_token by name, so we patch it where it's actually
    called from (app.service.auth_service), not just in google_oauth."""
    from app.service import auth_service

    fake_profile = GoogleProfile(google_id=google_id, email=email, full_name=full_name)
    monkeypatch.setattr(auth_service, "verify_google_id_token", lambda token: fake_profile)


def test_first_google_signin_becomes_admin(client, monkeypatch):
    _mock_google_profile(monkeypatch)
    res = client.post("/auth/google", json={"id_token": "fake-token"})
    assert res.status_code == 200
    assert res.json()["user"]["is_admin"] is True
    assert res.json()["user"]["email"] == "orok@gmail.com"


def test_second_google_signin_is_not_admin(client, monkeypatch, admin_token):
    _mock_google_profile(monkeypatch, google_id="g-456", email="second@gmail.com")
    res = client.post("/auth/google", json={"id_token": "fake-token"})
    assert res.status_code == 200
    assert res.json()["user"]["is_admin"] is False


def test_same_google_account_signs_in_on_repeat_visit(client, monkeypatch):
    _mock_google_profile(monkeypatch, google_id="g-123", email="orok@gmail.com")
    first = client.post("/auth/google", json={"id_token": "fake-token"})
    second = client.post("/auth/google", json={"id_token": "fake-token"})

    assert first.json()["user"]["id"] == second.json()["user"]["id"]
    assert second.json()["user"]["is_admin"] is True  # still the original first-user admin


def test_google_signin_links_to_existing_password_account_with_same_email(client, monkeypatch):
    signup_res = client.post(
        "/auth/signup",
        json={"full_name": "Existing User", "email": "existing@gmail.com", "password": "password123"},
    )
    existing_id = signup_res.json()["user"]["id"]

    _mock_google_profile(monkeypatch, google_id="g-789", email="existing@gmail.com", full_name="Existing User")
    google_res = client.post("/auth/google", json={"id_token": "fake-token"})

    # Same user record, not a new one -- Google was linked, not duplicated.
    assert google_res.json()["user"]["id"] == existing_id


def test_google_only_account_cannot_log_in_with_password(client, monkeypatch):
    _mock_google_profile(monkeypatch, google_id="g-999", email="googleonly@gmail.com")
    client.post("/auth/google", json={"id_token": "fake-token"})

    res = client.post("/auth/login", json={"email": "googleonly@gmail.com", "password": "anything"})
    assert res.status_code == 401


def test_deactivated_user_cannot_sign_in_with_google(client, monkeypatch, admin_token):
    _mock_google_profile(monkeypatch, google_id="g-111", email="blocked@gmail.com")
    first = client.post("/auth/google", json={"id_token": "fake-token"})
    user_id = first.json()["user"]["id"]

    client.patch(f"/users/{user_id}/status", json={"is_active": False}, headers=auth_headers(admin_token))

    res = client.post("/auth/google", json={"id_token": "fake-token"})
    assert res.status_code == 403
