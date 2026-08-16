import hashlib

from app.config.settings import get_settings
from app.service import paga_service


def test_kobo_to_naira_conversion():
    assert paga_service.kobo_to_naira(850000) == 8500.0
    assert paga_service.kobo_to_naira(150) == 1.5
    assert paga_service.kobo_to_naira(0) == 0.0


def test_sha512_hash_matches_manual_computation():
    result = paga_service._sha512_hash("abc", "123", "test-hash-key")
    expected = hashlib.sha512("abc123test-hash-key".encode("utf-8")).hexdigest()
    assert result == expected


def test_is_status_fully_paid_true_when_amounts_match():
    assert paga_service.is_status_fully_paid({"requestAmount": 8500.0, "totalPaymentAmount": 8500.0}) is True


def test_is_status_fully_paid_true_on_overpayment():
    assert paga_service.is_status_fully_paid({"requestAmount": 8500.0, "totalPaymentAmount": 9000.0}) is True


def test_is_status_fully_paid_false_when_underpaid():
    assert paga_service.is_status_fully_paid({"requestAmount": 8500.0, "totalPaymentAmount": 4000.0}) is False


def test_is_status_fully_paid_false_when_fields_missing():
    assert paga_service.is_status_fully_paid({}) is False


def test_is_status_fully_paid_reads_nested_data_key():
    """The /status endpoint's sample response wraps the fields in a
    top-level "data" object -- this must be unwrapped correctly."""
    payload = {"data": {"requestAmount": 7000.0, "totalPaymentAmount": 7048.38}}
    assert paga_service.is_status_fully_paid(payload) is True


def test_verify_webhook_hash_accepts_a_correctly_signed_payload(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "PAGA_PUBLIC_KEY", "pub")
    monkeypatch.setattr(settings, "PAGA_SECRET_KEY", "sec")
    monkeypatch.setattr(settings, "PAGA_HASH_KEY", "hashkey123")

    # No outstandingBalance in the payload -- per docs this contributes ""
    # to the concatenation rather than being skipped as a field entirely.
    correct_hash = hashlib.sha512(
        "notif-10order-abcCONSUMEDhashkey123".encode("utf-8")
    ).hexdigest()

    payload = {
        "notificationId": "notif-1",
        "statusCode": "0",
        "externalReferenceNumber": "order-abc",
        "state": "CONSUMED",
        "hash": correct_hash,
    }
    assert paga_service.verify_webhook_hash(payload) is True


def test_verify_webhook_hash_rejects_a_tampered_payload(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "PAGA_PUBLIC_KEY", "pub")
    monkeypatch.setattr(settings, "PAGA_SECRET_KEY", "sec")
    monkeypatch.setattr(settings, "PAGA_HASH_KEY", "hashkey123")

    payload = {
        "notificationId": "notif-1",
        "statusCode": "0",
        "externalReferenceNumber": "order-abc",
        "state": "CONSUMED",
        "hash": "deliberately-wrong-hash",
    }
    assert paga_service.verify_webhook_hash(payload) is False


def test_verify_webhook_hash_formats_outstanding_balance_to_two_decimals(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "PAGA_PUBLIC_KEY", "pub")
    monkeypatch.setattr(settings, "PAGA_SECRET_KEY", "sec")
    monkeypatch.setattr(settings, "PAGA_HASH_KEY", "hashkey123")

    # outstandingBalance present (partial payment case): docs specify it's
    # formatted to two decimal places, no thousands separator, when
    # included in the hash.
    correct_hash = hashlib.sha512(
        "notif-20foo0123.45hashkey123".encode("utf-8")
    ).hexdigest()

    payload = {
        "notificationId": "notif-2",
        "statusCode": "0",
        "externalReferenceNumber": "foo",
        "state": "0",
        "outstandingBalance": 123.45,
        "hash": correct_hash,
    }
    assert paga_service.verify_webhook_hash(payload) is True


def test_verify_webhook_hash_changes_when_outstanding_balance_present_vs_absent(monkeypatch):
    """Confirms outstandingBalance actually participates in the hash --
    a regression here would silently make partial-payment webhooks
    unverifiable."""
    settings = get_settings()
    monkeypatch.setattr(settings, "PAGA_PUBLIC_KEY", "pub")
    monkeypatch.setattr(settings, "PAGA_SECRET_KEY", "sec")
    monkeypatch.setattr(settings, "PAGA_HASH_KEY", "hashkey123")

    base = {
        "notificationId": "notif-3",
        "statusCode": "0",
        "externalReferenceNumber": "bar",
        "state": "CONSUMED",
    }

    hash_without_balance = paga_service._sha512_hash(
        base["notificationId"], base["statusCode"], base["externalReferenceNumber"], base["state"], "", "hashkey123"
    )
    hash_with_balance = paga_service._sha512_hash(
        base["notificationId"], base["statusCode"], base["externalReferenceNumber"], base["state"], "50.00", "hashkey123"
    )
    assert hash_without_balance != hash_with_balance