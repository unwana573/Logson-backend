from test.conftest import auth_headers


def test_anyone_can_list_categories(client):
    res = client.get("/categories")
    assert res.status_code == 200
    assert res.json() == []


def test_non_admin_cannot_create_category(client, user_token):
    res = client.post("/categories", json={"name": "Security"}, headers=auth_headers(user_token))
    assert res.status_code == 403


def test_admin_can_create_category(client, admin_token):
    res = client.post("/categories", json={"name": "Security"}, headers=auth_headers(admin_token))
    assert res.status_code == 201
    assert res.json()["name"] == "Security"
    assert res.json()["product_count"] == 0


def test_duplicate_category_name_is_rejected(client, admin_token):
    client.post("/categories", json={"name": "Security"}, headers=auth_headers(admin_token))
    res = client.post("/categories", json={"name": "Security"}, headers=auth_headers(admin_token))
    assert res.status_code == 400
