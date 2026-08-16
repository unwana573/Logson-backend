import hashlib
from dataclasses import dataclass
from typing import Optional

import requests
from fastapi import HTTPException
from requests.auth import HTTPBasicAuth

from app.config.settings import get_settings

settings = get_settings()


def _require_configured() -> None:
    if not (settings.PAGA_PUBLIC_KEY and settings.PAGA_SECRET_KEY and settings.PAGA_HASH_KEY):
        raise HTTPException(
            status_code=500,
            detail="PAGA_PUBLIC_KEY, PAGA_SECRET_KEY, and PAGA_HASH_KEY must all be configured on the server",
        )


def _sha512_hash(*parts: str) -> str:
    """Every Paga Collect request is signed by concatenating specific
    fields (in an exact, endpoint-specific order) plus the pre-shared hash
    key, then SHA-512 hashing the result. Missing/omitted optional fields
    contribute an empty string rather than being skipped entirely.

    Reference: https://developer-docs.paga.com/docs/handling-hash
    """
    return hashlib.sha512("".join(parts).encode("utf-8")).hexdigest()


def kobo_to_naira(amount_kobo: int) -> float:
    """Paga's amount field is a plain Naira number (e.g. 2000 = ₦2,000),
    unlike Paystack (which this project used to integrate with) which wants
    the smallest currency unit (kobo). Every
    product price in this app is stored in kobo, so this conversion has to
    happen at the boundary to the Paga client -- get it wrong and every
    charge is 100x off."""
    return round(amount_kobo / 100, 2)


@dataclass
class PagaPaymentRequestResult:
    reference_number: str
    web_payment_link: Optional[str]
    bank_transfer_account_number: Optional[str]
    ussd_short_code: Optional[str]
    expiry_datetime_utc: Optional[str]


def create_payment_request(
    *, reference_number: str, amount_kobo: int, payer_name: str, payer_email: str, callback_url: str
) -> PagaPaymentRequestResult:
    """Registers a new payment request with Paga. No payee account details
    are supplied, which per Paga's docs means the payment request
    processor (i.e. our own merchant account) is automatically selected as
    the recipient -- the simplest setup for a single-merchant store.

    Reference: https://developer-docs.paga.com/docs/request-payment
    """
    _require_configured()

    amount_naira = kobo_to_naira(amount_kobo)
    currency = "NGN"

    # Hash field order for /paymentRequest, per docs: referenceNumber +
    # amount + currency + payer.phoneNumber + payer.email +
    # payee.accountNumber + payee.phoneNumber + payee.bankId +
    # payee.bankAccountNumber + hashKey. We don't collect payer phone or
    # any payee override fields, so those contribute "".
    hash_value = _sha512_hash(
        reference_number,
        str(amount_naira),
        currency,
        "",  # payer.phoneNumber
        payer_email,
        "",  # payee.accountNumber
        "",  # payee.phoneNumber
        "",  # payee.bankId
        "",  # payee.bankAccountNumber
        settings.PAGA_HASH_KEY,
    )

    resp = requests.post(
        f"{settings.PAGA_BASE_URL}/paymentRequest",
        auth=HTTPBasicAuth(settings.PAGA_PUBLIC_KEY, settings.PAGA_SECRET_KEY),
        headers={"Content-Type": "application/json", "Accept": "application/json", "hash": hash_value},
        json={
            "referenceNumber": reference_number,
            "amount": amount_naira,
            "currency": currency,
            "payer": {"name": payer_name, "email": payer_email},
            "payee": {"name": settings.PAGA_PAYEE_NAME},
            "isSuppressMessages": False,
            "payerCollectionFeeShare": 1.0,
            "payeeCollectionFeeShare": 0.0,
            "isAllowPartialPayments": False,
            "isAllowOverPayments": False,
            "callBackUrl": callback_url,
            "paymentMethods": ["BANK_TRANSFER", "FUNDING_USSD", "REQUEST_MONEY"],
        },
        timeout=15,
    )

    try:
        data = resp.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="Paga returned an unreadable response")

    if data.get("statusCode") != "0":
        raise HTTPException(
            status_code=502,
            detail=f"Could not start Paga payment request: {data.get('statusMessage', 'unknown error')}",
        )

    web_link = None
    bank_account = None
    ussd_code = None
    for method in data.get("paymentMethods", []):
        props = method.get("properties", {})
        if method.get("name") == "REQUEST_MONEY":
            web_link = props.get("WebPaymentLink")
        elif method.get("name") == "BANK_TRANSFER":
            bank_account = props.get("AccountNumber")
        elif method.get("name") == "FUNDING_USSD":
            ussd_code = props.get("USSDShortCode")

    return PagaPaymentRequestResult(
        reference_number=data.get("referenceNumber", reference_number),
        web_payment_link=web_link,
        bank_transfer_account_number=bank_account,
        ussd_short_code=ussd_code,
        expiry_datetime_utc=data.get("expiryDateTimeUTC"),
    )


def get_payment_status(reference_number: str) -> dict:
    """Polls the status of a payment request. Paga's own guidance is to
    rely on the webhook callback rather than polling this repeatedly (see
    paga_webhook in order_service.py) -- this is offered as a fallback for
    an explicit "check now" action, not a substitute for the webhook.

    Reference: https://developer-docs.paga.com/docs/status
    """
    _require_configured()

    # Hash field order for /status: referenceNumber + hashKey
    hash_value = _sha512_hash(reference_number, settings.PAGA_HASH_KEY)

    resp = requests.post(
        f"{settings.PAGA_BASE_URL}/status",
        auth=HTTPBasicAuth(settings.PAGA_PUBLIC_KEY, settings.PAGA_SECRET_KEY),
        headers={"Content-Type": "application/json", "Accept": "application/json", "hash": hash_value},
        json={"referenceNumber": reference_number},
        timeout=15,
    )

    try:
        return resp.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="Paga returned an unreadable response")


def is_status_fully_paid(status_data: dict) -> bool:
    """Paga's /status response doesn't include an explicit paid/unpaid
    boolean in its documented shape -- the documented fields are
    requestAmount and totalPaymentAmount. Treating "total paid >= amount
    requested" as fulfilled is the documented-but-inferred signal; the
    webhook's explicit `state: "CONSUMED"` (see verify_webhook_hash below)
    is the authoritative signal and should be preferred wherever possible."""
    inner = status_data.get("data", status_data)
    requested = inner.get("requestAmount")
    paid = inner.get("totalPaymentAmount")
    if requested is None or paid is None:
        return False
    return paid >= requested


def verify_webhook_hash(payload: dict) -> bool:
    """Verifies a Payment Request callback notification actually came from
    Paga and wasn't tampered with, per the documented hash scheme for
    section 14 (Payment Request Callback notifications): SHA-512 of
    notificationId + statusCode + externalReferenceNumber + state +
    outstandingBalance + hashKey. `outstandingBalance` is formatted to two
    decimal places if present, and contributes "" if null/absent.

    Reference: https://developer-docs.paga.com/docs/operations-1#14-payment-request-callback-notifications
    """
    _require_configured()

    outstanding = payload.get("outstandingBalance")
    outstanding_str = f"{outstanding:.2f}" if outstanding is not None else ""

    expected = _sha512_hash(
        str(payload.get("notificationId", "")),
        str(payload.get("statusCode", "")),
        str(payload.get("externalReferenceNumber", "")),
        str(payload.get("state", "")),
        outstanding_str,
        settings.PAGA_HASH_KEY,
    )
    return expected == payload.get("hash")