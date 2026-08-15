from test.conftest import auth_headers


def _get_user_id(client, token, email):
    res = client.get("/auth/me", headers=auth_headers(token))
    assert res.json()["email"] == email
    return res.json()["id"]


def test_non_admin_cannot_list_users(client, user_token):
    res = client.get("/users", headers=auth_headers(user_token))
    assert res.status_code == 403


def test_admin_can_list_users(client, admin_token, user_token):
    res = client.get("/users", headers=auth_headers(admin_token))
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_non_admin_cannot_promote_self(client, admin_token, user_token):
    user_id = _get_user_id(client, user_token, "user@logson.ng")
    res = client.patch(
        f"/users/{user_id}/role", json={"is_admin": True}, headers=auth_headers(user_token)
    )
    assert res.status_code == 403


def test_admin_can_promote_another_user(client, admin_token, user_token):
    user_id = _get_user_id(client, user_token, "user@logson.ng")
    res = client.patch(
        f"/users/{user_id}/role", json={"is_admin": True}, headers=auth_headers(admin_token)
    )
    assert res.status_code == 200
    assert res.json()["is_admin"] is True


def test_admin_cannot_remove_their_own_admin_access(client, admin_token):
    admin_id = _get_user_id(client, admin_token, "admin@logson.ng")
    res = client.patch(
        f"/users/{admin_id}/role", json={"is_admin": False}, headers=auth_headers(admin_token)
    )
    assert res.status_code == 400


def test_admin_can_deactivate_another_user(client, admin_token, user_token):
    user_id = _get_user_id(client, user_token, "user@logson.ng")
    res = client.patch(
        f"/users/{user_id}/status", json={"is_active": False}, headers=auth_headers(admin_token)
    )
    assert res.status_code == 200
    assert res.json()["is_active"] is False


def test_deactivated_user_cannot_authenticate(client, admin_token, user_token):
    user_id = _get_user_id(client, user_token, "user@logson.ng")
    client.patch(f"/users/{user_id}/status", json={"is_active": False}, headers=auth_headers(admin_token))

    res = client.get("/auth/me", headers=auth_headers(user_token))
    assert res.status_code == 403
