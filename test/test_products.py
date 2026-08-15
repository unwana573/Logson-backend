from test.conftest import auth_headers


def _create_category(client, admin_token, name="Operating systems"):
    res = client.post("/categories", json={"name": name}, headers=auth_headers(admin_token))
    return res.json()["id"]


def test_non_admin_cannot_create_product(client, admin_token, user_token):
    category_id = _create_category(client, admin_token)
    res = client.post(
        "/products",
        json={"name": "Windows 11 Pro", "vendor": "Microsoft", "category_id": category_id, "price_kobo": 850000},
        headers=auth_headers(user_token),
    )
    assert res.status_code == 403


def test_admin_creates_product_with_bulk_stock_textarea(client, admin_token):
    category_id = _create_category(client, admin_token)
    res = client.post(
        "/products",
        json={
            "name": "Windows 11 Pro",
            "vendor": "Microsoft",
            "category_id": category_id,
            "price_kobo": 850000,
            "stock_text": "AAAAA-BBBBB\nCCCCC-DDDDD\nEEEEE-FFFFF\n",
        },
        headers=auth_headers(admin_token),
    )
    assert res.status_code == 201
    # Each non-empty line becomes exactly one stock unit.
    assert res.json()["stock_count"] == 3


def test_blank_lines_in_stock_textarea_are_ignored(client, admin_token):
    category_id = _create_category(client, admin_token)
    res = client.post(
        "/products",
        json={
            "name": "Adobe Creative Cloud",
            "vendor": "Adobe",
            "category_id": category_id,
            "price_kobo": 4200000,
            "stock_text": "KEY-ONE\n\n  \nKEY-TWO\n",
        },
        headers=auth_headers(admin_token),
    )
    assert res.json()["stock_count"] == 2


def test_search_matches_product_name(client, admin_token):
    category_id = _create_category(client, admin_token)
    client.post(
        "/products",
        json={"name": "Windows 11 Pro", "vendor": "Microsoft", "category_id": category_id, "price_kobo": 850000},
        headers=auth_headers(admin_token),
    )
    client.post(
        "/products",
        json={"name": "Adobe Creative Cloud", "vendor": "Adobe", "category_id": category_id, "price_kobo": 4200000},
        headers=auth_headers(admin_token),
    )

    res = client.get("/products", params={"search": "windows"})
    names = [p["name"] for p in res.json()]
    assert names == ["Windows 11 Pro"]


def test_search_matches_vendor_case_insensitively(client, admin_token):
    category_id = _create_category(client, admin_token)
    client.post(
        "/products",
        json={"name": "Creative Cloud", "vendor": "Adobe", "category_id": category_id, "price_kobo": 4200000},
        headers=auth_headers(admin_token),
    )

    res = client.get("/products", params={"search": "ADOBE"})
    assert len(res.json()) == 1
    assert res.json()[0]["vendor"] == "Adobe"


def test_search_with_no_match_returns_empty_list(client, admin_token):
    res = client.get("/products", params={"search": "nonexistent-product"})
    assert res.status_code == 200
    assert res.json() == []
