from test.conftest import auth_headers


def test_anyone_can_list_categories(client):
    res = client.get("/categories")
    assert res.status_code == 200
    assert res.json() == []


# ---------- Create ----------

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


def test_created_category_appears_in_list(client, admin_token):
    client.post("/categories", json={"name": "Design tools"}, headers=auth_headers(admin_token))
    res = client.get("/categories")
    names = [c["name"] for c in res.json()]
    assert "Design tools" in names


# ---------- Update ----------

def test_non_admin_cannot_update_category(client, admin_token, user_token):
    created = client.post("/categories", json={"name": "Security"}, headers=auth_headers(admin_token)).json()
    res = client.patch(
        f"/categories/{created['id']}", json={"name": "Cybersecurity"}, headers=auth_headers(user_token)
    )
    assert res.status_code == 403


def test_admin_can_rename_category(client, admin_token):
    created = client.post("/categories", json={"name": "Security"}, headers=auth_headers(admin_token)).json()
    res = client.patch(
        f"/categories/{created['id']}", json={"name": "Cybersecurity"}, headers=auth_headers(admin_token)
    )
    assert res.status_code == 200
    assert res.json()["name"] == "Cybersecurity"

    # The rename is persisted, not just returned in the response.
    listed = client.get("/categories").json()
    names = [c["name"] for c in listed]
    assert "Cybersecurity" in names
    assert "Security" not in names


def test_updating_nonexistent_category_returns_404(client, admin_token):
    res = client.patch(
        "/categories/does-not-exist", json={"name": "Whatever"}, headers=auth_headers(admin_token)
    )
    assert res.status_code == 404


def test_renaming_to_an_existing_name_is_rejected(client, admin_token):
    client.post("/categories", json={"name": "Security"}, headers=auth_headers(admin_token))
    other = client.post(
        "/categories", json={"name": "Office suites"}, headers=auth_headers(admin_token)
    ).json()

    res = client.patch(
        f"/categories/{other['id']}", json={"name": "Security"}, headers=auth_headers(admin_token)
    )
    assert res.status_code == 400


def test_renaming_a_category_to_its_own_current_name_is_allowed(client, admin_token):
    """Not a real rename, but shouldn't trip the duplicate-name check
    against itself."""
    created = client.post("/categories", json={"name": "Security"}, headers=auth_headers(admin_token)).json()
    res = client.patch(
        f"/categories/{created['id']}", json={"name": "Security"}, headers=auth_headers(admin_token)
    )
    assert res.status_code == 200


# ---------- Delete ----------

def test_non_admin_cannot_delete_category(client, admin_token, user_token):
    created = client.post("/categories", json={"name": "Security"}, headers=auth_headers(admin_token)).json()
    res = client.delete(f"/categories/{created['id']}", headers=auth_headers(user_token))
    assert res.status_code == 403


def test_admin_can_delete_an_empty_category(client, admin_token):
    created = client.post("/categories", json={"name": "Security"}, headers=auth_headers(admin_token)).json()
    res = client.delete(f"/categories/{created['id']}", headers=auth_headers(admin_token))
    assert res.status_code == 204

    listed = client.get("/categories").json()
    assert created["id"] not in [c["id"] for c in listed]


def test_deleting_nonexistent_category_returns_404(client, admin_token):
    res = client.delete("/categories/does-not-exist", headers=auth_headers(admin_token))
    assert res.status_code == 404


def test_cannot_delete_a_category_with_products_in_it(client, admin_token):
    category = client.post("/categories", json={"name": "Security"}, headers=auth_headers(admin_token)).json()
    client.post(
        "/products",
        json={
            "name": "Malwarebytes Premium",
            "vendor": "Malwarebytes",
            "category_id": category["id"],
            "price_kobo": 620000,
        },
        headers=auth_headers(admin_token),
    )

    res = client.delete(f"/categories/{category['id']}", headers=auth_headers(admin_token))
    assert res.status_code == 400

    # Still there afterward -- the failed delete must not have removed it.
    listed = client.get("/categories").json()
    assert category["id"] in [c["id"] for c in listed]


# ---------- Full lifecycle, in one place ----------

def test_full_category_crud_lifecycle(client, admin_token):
    # Create
    created = client.post(
        "/categories", json={"name": "VPN services"}, headers=auth_headers(admin_token)
    ).json()
    assert created["name"] == "VPN services"

    # Read (via list -- there's no single-category GET, listing is the read path)
    listed = client.get("/categories").json()
    assert created["id"] in [c["id"] for c in listed]

    # Update
    updated_res = client.patch(
        f"/categories/{created['id']}", json={"name": "VPN & Privacy"}, headers=auth_headers(admin_token)
    )
    assert updated_res.status_code == 200
    assert updated_res.json()["name"] == "VPN & Privacy"

    # Delete
    delete_res = client.delete(f"/categories/{created['id']}", headers=auth_headers(admin_token))
    assert delete_res.status_code == 204

    final_listed = client.get("/categories").json()
    assert created["id"] not in [c["id"] for c in final_listed]