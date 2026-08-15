from test.conftest import auth_headers


def _create_product(client, admin_token, stock_text="AAAAA-BBBBB\nCCCCC-DDDDD"):
    cat = client.post("/categories", json={"name": "Operating systems"}, headers=auth_headers(admin_token))
    category_id = cat.json()["id"]
    res = client.post(
        "/products",
        json={
            "name": "Windows 11 Pro",
            "vendor": "Microsoft",
            "category_id": category_id,
            "price_kobo": 850000,
            "stock_text": stock_text,
        },
        headers=auth_headers(admin_token),
    )
    return res.json()["id"]


def test_manual_order_requires_proof_url(client, admin_token, user_token):
    product_id = _create_product(client, admin_token)
    res = client.post(
        "/orders",
        json={"product_id": product_id, "quantity": 1, "payment_method": "manual"},
        headers=auth_headers(user_token),
    )
    assert res.status_code == 400


def test_manual_order_starts_pending(client, admin_token, user_token):
    product_id = _create_product(client, admin_token)
    res = client.post(
        "/orders",
        json={
            "product_id": product_id,
            "quantity": 1,
            "payment_method": "manual",
            "proof_url": "https://example.com/proof.jpg",
        },
        headers=auth_headers(user_token),
    )
    assert res.status_code == 201
    assert res.json()["status"] == "pending"


def test_order_exceeding_stock_is_rejected(client, admin_token, user_token):
    product_id = _create_product(client, admin_token, stock_text="ONLY-ONE-KEY")
    res = client.post(
        "/orders",
        json={
            "product_id": product_id,
            "quantity": 5,
            "payment_method": "manual",
            "proof_url": "https://example.com/proof.jpg",
        },
        headers=auth_headers(user_token),
    )
    assert res.status_code == 409


def test_non_admin_cannot_approve_orders(client, admin_token, user_token):
    product_id = _create_product(client, admin_token)
    order = client.post(
        "/orders",
        json={
            "product_id": product_id,
            "quantity": 1,
            "payment_method": "manual",
            "proof_url": "https://example.com/proof.jpg",
        },
        headers=auth_headers(user_token),
    ).json()

    res = client.post(f"/orders/{order['id']}/approve", headers=auth_headers(user_token))
    assert res.status_code == 403


def test_admin_approval_assigns_credential_and_credits_amount_spent(client, admin_token, user_token):
    product_id = _create_product(client, admin_token, stock_text="VK7DX-9F3QM-2LWRT")
    order = client.post(
        "/orders",
        json={
            "product_id": product_id,
            "quantity": 1,
            "payment_method": "manual",
            "proof_url": "https://example.com/proof.jpg",
        },
        headers=auth_headers(user_token),
    ).json()

    approve_res = client.post(f"/orders/{order['id']}/approve", headers=auth_headers(admin_token))
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "success"

    me = client.get("/auth/me", headers=auth_headers(user_token)).json()
    assert me["amount_spent_kobo"] == 850000

    creds = client.get("/users/me/credentials", headers=auth_headers(user_token)).json()
    assert len(creds) == 1
    assert creds[0]["credential"] == "VK7DX-9F3QM-2LWRT"


def test_cannot_approve_an_order_twice(client, admin_token, user_token):
    product_id = _create_product(client, admin_token)
    order = client.post(
        "/orders",
        json={
            "product_id": product_id,
            "quantity": 1,
            "payment_method": "manual",
            "proof_url": "https://example.com/proof.jpg",
        },
        headers=auth_headers(user_token),
    ).json()

    client.post(f"/orders/{order['id']}/approve", headers=auth_headers(admin_token))
    second = client.post(f"/orders/{order['id']}/approve", headers=auth_headers(admin_token))
    assert second.status_code == 400


def test_user_sees_only_their_own_orders(client, admin_token, user_token):
    product_id = _create_product(client, admin_token, stock_text="A\nB\nC\nD")

    # admin places an order too
    client.post(
        "/orders",
        json={
            "product_id": product_id,
            "quantity": 1,
            "payment_method": "manual",
            "proof_url": "https://example.com/proof.jpg",
        },
        headers=auth_headers(admin_token),
    )
    client.post(
        "/orders",
        json={
            "product_id": product_id,
            "quantity": 1,
            "payment_method": "manual",
            "proof_url": "https://example.com/proof.jpg",
        },
        headers=auth_headers(user_token),
    )

    res = client.get("/orders/me", headers=auth_headers(user_token))
    assert len(res.json()) == 1


def test_admin_sees_all_orders(client, admin_token, user_token):
    product_id = _create_product(client, admin_token, stock_text="A\nB")
    client.post(
        "/orders",
        json={
            "product_id": product_id,
            "quantity": 1,
            "payment_method": "manual",
            "proof_url": "https://example.com/proof.jpg",
        },
        headers=auth_headers(user_token),
    )

    res = client.get("/orders", headers=auth_headers(admin_token))
    assert res.status_code == 200
    assert len(res.json()) == 1
