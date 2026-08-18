import base64

from test.conftest import auth_headers

# A real (tiny) 1x1 PNG. Only its leading magic bytes matter to the upload
# endpoint's sniffer, but a genuine image keeps the test honest.
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)


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


def _create_manual_order(client, token, product_id, quantity=1):
    return client.post(
        "/orders",
        json={"product_id": product_id, "quantity": quantity, "payment_method": "manual"},
        headers=auth_headers(token),
    )


def _upload_proof(client, token, order_id, data=PNG_BYTES, content_type="image/png", filename="proof.png"):
    return client.post(
        f"/orders/{order_id}/proof",
        files={"file": (filename, data, content_type)},
        headers=auth_headers(token),
    )


def test_manual_order_creates_pending_without_proof(client, admin_token, user_token):
    # Proof now arrives in a separate upload step, so creating a manual order
    # no longer needs it -- it just starts pending and unproven.
    product_id = _create_product(client, admin_token)
    res = _create_manual_order(client, user_token, product_id)
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "pending"
    assert body["has_proof"] is False


def test_order_exceeding_stock_is_rejected(client, admin_token, user_token):
    product_id = _create_product(client, admin_token, stock_text="ONLY-ONE-KEY")
    res = client.post(
        "/orders",
        json={"product_id": product_id, "quantity": 5, "payment_method": "manual"},
        headers=auth_headers(user_token),
    )
    assert res.status_code == 409


def test_upload_proof_marks_order_has_proof(client, admin_token, user_token):
    product_id = _create_product(client, admin_token)
    order = _create_manual_order(client, user_token, product_id).json()

    res = _upload_proof(client, user_token, order["id"])
    assert res.status_code == 200
    assert res.json()["has_proof"] is True


def test_reject_non_image_upload(client, admin_token, user_token):
    product_id = _create_product(client, admin_token)
    order = _create_manual_order(client, user_token, product_id).json()

    res = _upload_proof(
        client, user_token, order["id"], data=b"i am definitely not an image", content_type="text/plain", filename="notes.txt"
    )
    assert res.status_code == 400


def test_reject_oversized_proof(client, admin_token, user_token):
    product_id = _create_product(client, admin_token)
    order = _create_manual_order(client, user_token, product_id).json()

    # PNG magic bytes followed by >5 MB of padding -- rejected on size before
    # the content is ever stored.
    oversized = b"\x89PNG\r\n\x1a\n" + b"\x00" * (5 * 1024 * 1024 + 1)
    res = _upload_proof(client, user_token, order["id"], data=oversized)
    assert res.status_code == 413


def test_get_proof_returns_stored_image(client, admin_token, user_token):
    product_id = _create_product(client, admin_token)
    order = _create_manual_order(client, user_token, product_id).json()
    _upload_proof(client, user_token, order["id"])

    res = client.get(f"/orders/{order['id']}/proof", headers=auth_headers(user_token))
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert res.content == PNG_BYTES


def test_get_proof_404_when_none_uploaded(client, admin_token, user_token):
    product_id = _create_product(client, admin_token)
    order = _create_manual_order(client, user_token, product_id).json()

    res = client.get(f"/orders/{order['id']}/proof", headers=auth_headers(user_token))
    assert res.status_code == 404


def test_admin_can_view_user_proof(client, admin_token, user_token):
    product_id = _create_product(client, admin_token)
    order = _create_manual_order(client, user_token, product_id).json()
    _upload_proof(client, user_token, order["id"])

    # An admin (not the owner) can still fetch the proof for the Payments view.
    res = client.get(f"/orders/{order['id']}/proof", headers=auth_headers(admin_token))
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"


def test_cannot_upload_proof_to_someone_elses_order(client, admin_token, user_token):
    product_id = _create_product(client, admin_token)
    admins_order = _create_manual_order(client, admin_token, product_id).json()

    # A different user can't attach proof to an order that isn't theirs. 404
    # (not 403) so we don't reveal that the order exists.
    res = _upload_proof(client, user_token, admins_order["id"])
    assert res.status_code == 404


def test_approve_without_proof_is_rejected(client, admin_token, user_token):
    product_id = _create_product(client, admin_token)
    order = _create_manual_order(client, user_token, product_id).json()

    # Admin can't approve a manual order that has no proof of payment attached.
    res = client.post(f"/orders/{order['id']}/approve", headers=auth_headers(admin_token))
    assert res.status_code == 400


def test_non_admin_cannot_approve_orders(client, admin_token, user_token):
    product_id = _create_product(client, admin_token)
    order = _create_manual_order(client, user_token, product_id).json()

    res = client.post(f"/orders/{order['id']}/approve", headers=auth_headers(user_token))
    assert res.status_code == 403


def test_admin_approval_assigns_credential_and_credits_amount_spent(client, admin_token, user_token):
    product_id = _create_product(client, admin_token, stock_text="VK7DX-9F3QM-2LWRT")
    order = _create_manual_order(client, user_token, product_id).json()
    _upload_proof(client, user_token, order["id"])

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
    order = _create_manual_order(client, user_token, product_id).json()
    _upload_proof(client, user_token, order["id"])

    client.post(f"/orders/{order['id']}/approve", headers=auth_headers(admin_token))
    second = client.post(f"/orders/{order['id']}/approve", headers=auth_headers(admin_token))
    assert second.status_code == 400


def test_user_sees_only_their_own_orders(client, admin_token, user_token):
    product_id = _create_product(client, admin_token, stock_text="A\nB\nC\nD")

    # admin places an order too
    _create_manual_order(client, admin_token, product_id)
    _create_manual_order(client, user_token, product_id)

    res = client.get("/orders/me", headers=auth_headers(user_token))
    assert len(res.json()) == 1


def test_admin_sees_all_orders(client, admin_token, user_token):
    product_id = _create_product(client, admin_token, stock_text="A\nB")
    _create_manual_order(client, user_token, product_id)

    res = client.get("/orders", headers=auth_headers(admin_token))
    assert res.status_code == 200
    assert len(res.json()) == 1
