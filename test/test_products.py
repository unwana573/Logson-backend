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


def test_product_can_be_created_without_stock_text(client, admin_token):
    """Supports the two-step admin flow: create the product first, add
    credentials afterward via POST /products/{id}/stock."""
    category_id = _create_category(client, admin_token)
    res = client.post(
        "/products",
        json={
            "name": "Windows 11 Pro",
            "vendor": "Microsoft",
            "category_id": category_id,
            "price_kobo": 850000,
        },
        headers=auth_headers(admin_token),
    )
    assert res.status_code == 201
    assert res.json()["stock_count"] == 0


def test_product_stores_and_returns_description(client, admin_token):
    category_id = _create_category(client, admin_token)
    res = client.post(
        "/products",
        json={
            "name": "Windows 11 Pro",
            "vendor": "Microsoft",
            "category_id": category_id,
            "price_kobo": 850000,
            "description": "Genuine retail license, single-device activation.",
        },
        headers=auth_headers(admin_token),
    )
    assert res.status_code == 201
    assert res.json()["description"] == "Genuine retail license, single-device activation."


def test_product_description_is_optional(client, admin_token):
    category_id = _create_category(client, admin_token)
    res = client.post(
        "/products",
        json={"name": "Windows 11 Pro", "vendor": "Microsoft", "category_id": category_id, "price_kobo": 850000},
        headers=auth_headers(admin_token),
    )
    assert res.status_code == 201
    assert res.json()["description"] is None


def test_admin_can_add_stock_to_a_product_after_creation(client, admin_token):
    """The credentials-added-in-a-second-step flow, end to end."""
    category_id = _create_category(client, admin_token)
    product = client.post(
        "/products",
        json={"name": "Windows 11 Pro", "vendor": "Microsoft", "category_id": category_id, "price_kobo": 850000},
        headers=auth_headers(admin_token),
    ).json()
    assert product["stock_count"] == 0

    res = client.post(
        f"/products/{product['id']}/stock",
        json={"stock_text": "AAAAA-BBBBB\nCCCCC-DDDDD"},
        headers=auth_headers(admin_token),
    )
    assert res.status_code == 200
    assert res.json()["stock_count"] == 2


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