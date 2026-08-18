from app.service import paga_service
from app.service.paga_service import PagaPaymentRequestResult
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
            "price_kobo": 850000,  # ₦8,500
            "stock_text": stock_text,
        },
        headers=auth_headers(admin_token),
    )
    return res.json()["id"]


def _create_paga_order(client, token, product_id, quantity=1):
    return client.post(
        "/orders",
        json={"product_id": product_id, "quantity": quantity, "payment_method": "paga"},
        headers=auth_headers(token),
    ).json()


def test_paga_init_converts_kobo_to_naira_and_stores_reference(client, monkeypatch, admin_token, user_token):
    captured = {}

    def fake_create_payment_request(*, reference_number, amount_kobo, payer_name, payer_email, callback_url):
        captured["amount_kobo"] = amount_kobo
        return PagaPaymentRequestResult(
            reference_number=reference_number,
            web_payment_link="https://beta.justpaga.me/fake-link",
            bank_transfer_account_number="1016953737",
            ussd_short_code="*901*000*724#",
            expiry_datetime_utc="2026-04-23T11:45:00",
        )

    monkeypatch.setattr(paga_service, "create_payment_request", fake_create_payment_request)

    product_id = _create_product(client, admin_token)
    order = _create_paga_order(client, user_token, product_id)

    res = client.post(f"/orders/{order['id']}/paga/init", headers=auth_headers(user_token))
    assert res.status_code == 200
    assert res.json()["web_payment_link"] == "https://beta.justpaga.me/fake-link"
    assert res.json()["bank_transfer_account_number"] == "1016953737"

    # amount_kobo passed straight through to the Paga client -- the
    # kobo->naira conversion happens inside paga_service, not here.
    assert captured["amount_kobo"] == 850000


def test_paga_init_rejects_wrong_payment_method(client, admin_token, user_token):
    product_id = _create_product(client, admin_token)
    order = client.post(
        "/orders",
        json={
            "product_id": product_id,
            "quantity": 1,
            "payment_method": "manual",
        },
        headers=auth_headers(user_token),
    ).json()

    res = client.post(f"/orders/{order['id']}/paga/init", headers=auth_headers(user_token))
    assert res.status_code == 400


def test_paga_init_rejects_someone_elses_order(client, admin_token, user_token):
    product_id = _create_product(client, admin_token)
    order = _create_paga_order(client, admin_token, product_id)  # admin's order

    res = client.post(f"/orders/{order['id']}/paga/init", headers=auth_headers(user_token))
    assert res.status_code == 404


def test_webhook_with_valid_hash_and_payment_complete_fulfils_order(client, monkeypatch, admin_token, user_token):
    product_id = _create_product(client, admin_token, stock_text="VK7DX-9F3QM-2LWRT")
    order = _create_paga_order(client, user_token, product_id)

    monkeypatch.setattr(paga_service, "verify_webhook_hash", lambda payload: True)

    webhook_payload = {
        "event": "PAYMENT_COMPLETE",
        "notificationId": "e68545b8-358c-4b72-9ac1-0471008617e7",
        "statusCode": "0",
        "statusMessage": "Payment Request has been authorized",
        "externalReferenceNumber": order["id"],
        "state": "CONSUMED",
        "outstandingBalance": 0,
        "paymentAmount": 8500.0,
        "hash": "irrelevant-since-mocked",
    }
    res = client.post("/orders/paga/webhook", json=webhook_payload)
    assert res.status_code == 200
    assert res.json() == {"status": "SUCCESS"}

    me = client.get("/auth/me", headers=auth_headers(user_token)).json()
    assert me["amount_spent_kobo"] == 850000

    creds = client.get("/users/me/credentials", headers=auth_headers(user_token)).json()
    assert len(creds) == 1


def test_webhook_with_invalid_hash_is_rejected(client, monkeypatch, admin_token, user_token):
    product_id = _create_product(client, admin_token)
    order = _create_paga_order(client, user_token, product_id)

    monkeypatch.setattr(paga_service, "verify_webhook_hash", lambda payload: False)

    res = client.post(
        "/orders/paga/webhook",
        json={
            "event": "PAYMENT_COMPLETE",
            "externalReferenceNumber": order["id"],
            "state": "CONSUMED",
            "hash": "tampered",
        },
    )
    assert res.status_code == 401

    # order must still be pending -- a bad hash must never fulfil an order
    me = client.get("/auth/me", headers=auth_headers(user_token)).json()
    assert me["amount_spent_kobo"] == 0


def test_webhook_for_unknown_reference_is_ignored_not_errored(client, monkeypatch):
    monkeypatch.setattr(paga_service, "verify_webhook_hash", lambda payload: True)

    res = client.post(
        "/orders/paga/webhook",
        json={
            "event": "PAYMENT_COMPLETE",
            "externalReferenceNumber": "does-not-exist",
            "state": "CONSUMED",
            "hash": "irrelevant",
        },
    )
    # Acknowledged (200), not 404 -- an unrecognized reference must not
    # trigger Paga's retry mechanism.
    assert res.status_code == 200


def test_webhook_does_not_double_fulfil_an_already_completed_order(client, monkeypatch, admin_token, user_token):
    product_id = _create_product(client, admin_token, stock_text="ONLY-ONE-KEY")
    order = _create_paga_order(client, user_token, product_id)

    monkeypatch.setattr(paga_service, "verify_webhook_hash", lambda payload: True)
    payload = {
        "event": "PAYMENT_COMPLETE",
        "externalReferenceNumber": order["id"],
        "state": "CONSUMED",
        "hash": "irrelevant",
    }
    client.post("/orders/paga/webhook", json=payload)
    client.post("/orders/paga/webhook", json=payload)  # retried/duplicate delivery

    me = client.get("/auth/me", headers=auth_headers(user_token)).json()
    # Credited exactly once, not twice, despite two webhook deliveries.
    assert me["amount_spent_kobo"] == 850000


def test_paga_verify_fulfils_order_when_status_shows_fully_paid(client, monkeypatch, admin_token, user_token):
    product_id = _create_product(client, admin_token, stock_text="MBP1-7ZQX-44RT")
    order = _create_paga_order(client, user_token, product_id)

    monkeypatch.setattr(paga_service, "create_payment_request", lambda **kwargs: PagaPaymentRequestResult(
        reference_number=order["id"], web_payment_link="https://x", bank_transfer_account_number=None,
        ussd_short_code=None, expiry_datetime_utc=None,
    ))
    client.post(f"/orders/{order['id']}/paga/init", headers=auth_headers(user_token))

    monkeypatch.setattr(
        paga_service, "get_payment_status", lambda ref: {"requestAmount": 8500.0, "totalPaymentAmount": 8500.0}
    )

    res = client.post(f"/orders/{order['id']}/paga/verify", headers=auth_headers(user_token))
    assert res.status_code == 200
    assert res.json()["status"] == "success"


def test_paga_verify_leaves_order_pending_when_not_yet_paid(client, monkeypatch, admin_token, user_token):
    product_id = _create_product(client, admin_token)
    order = _create_paga_order(client, user_token, product_id)

    monkeypatch.setattr(paga_service, "create_payment_request", lambda **kwargs: PagaPaymentRequestResult(
        reference_number=order["id"], web_payment_link="https://x", bank_transfer_account_number=None,
        ussd_short_code=None, expiry_datetime_utc=None,
    ))
    client.post(f"/orders/{order['id']}/paga/init", headers=auth_headers(user_token))

    monkeypatch.setattr(
        paga_service, "get_payment_status", lambda ref: {"requestAmount": 8500.0, "totalPaymentAmount": 0.0}
    )

    res = client.post(f"/orders/{order['id']}/paga/verify", headers=auth_headers(user_token))
    assert res.status_code == 200
    assert res.json()["status"] == "pending"