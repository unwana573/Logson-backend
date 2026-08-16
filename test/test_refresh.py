from test.conftest import auth_headers


def test_signup_response_includes_refresh_token(client):
    res = client.post(
        "/auth/signup",
        json={"full_name": "Orok Dev", "email": "orok@logson.ng", "password": "password123"},
    )
    assert "refresh_token" in res.json()
    assert res.json()["refresh_token"] != res.json()["access_token"]


def test_refresh_returns_a_new_valid_access_token(client, admin_token):
    login_res = client.post("/auth/login", json={"email": "admin@logson.ng", "password": "password123"})
    refresh_token = login_res.json()["refresh_token"]

    refresh_res = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_res.status_code == 200

    new_access_token = refresh_res.json()["access_token"]
    me = client.get("/auth/me", headers=auth_headers(new_access_token))
    assert me.status_code == 200
    assert me.json()["email"] == "admin@logson.ng"


def test_refresh_rejects_an_access_token(client, admin_token):
    """An access token has type=access, not type=refresh -- POST /auth/refresh
    must not accept it even though it's a validly signed token."""
    res = client.post("/auth/refresh", json={"refresh_token": admin_token})
    assert res.status_code == 401


def test_refresh_rejects_garbage_token(client):
    res = client.post("/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert res.status_code == 401


def test_refresh_rejects_deactivated_user(client, admin_token, user_token):
    login_res = client.post("/auth/login", json={"email": "user@logson.ng", "password": "password123"})
    refresh_token = login_res.json()["refresh_token"]

    me = client.get("/auth/me", headers=auth_headers(user_token)).json()
    client.patch(f"/users/{me['id']}/status", json={"is_active": False}, headers=auth_headers(admin_token))

    res = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert res.status_code == 403