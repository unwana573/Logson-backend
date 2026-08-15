from test.conftest import auth_headers


def test_first_signup_becomes_admin(client):
    res = client.post(
        "/auth/signup",
        json={"full_name": "Orok Dev", "email": "orok@logson.ng", "password": "password123"},
    )
    assert res.status_code == 201
    assert res.json()["user"]["is_admin"] is True


def test_second_signup_is_not_admin(client, admin_token):
    res = client.post(
        "/auth/signup",
        json={"full_name": "Chidi O", "email": "chidi@logson.ng", "password": "password123"},
    )
    assert res.status_code == 201
    assert res.json()["user"]["is_admin"] is False


def test_signup_with_existing_email_is_rejected(client, admin_token):
    res = client.post(
        "/auth/signup",
        json={"full_name": "Duplicate", "email": "admin@logson.ng", "password": "password123"},
    )
    assert res.status_code == 400


def test_login_with_correct_credentials(client, admin_token):
    res = client.post("/auth/login", json={"email": "admin@logson.ng", "password": "password123"})
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_with_wrong_password_fails(client, admin_token):
    res = client.post("/auth/login", json={"email": "admin@logson.ng", "password": "wrong-password"})
    assert res.status_code == 401


def test_me_requires_a_valid_token(client, admin_token):
    res = client.get("/auth/me", headers=auth_headers(admin_token))
    assert res.status_code == 200
    assert res.json()["email"] == "admin@logson.ng"

    res_no_auth = client.get("/auth/me")
    assert res_no_auth.status_code == 401
