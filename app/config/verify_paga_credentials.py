"""
Verifies your Paga credentials actually work, by making one real call to
Paga's sandbox -- separate from the app, separate from pytest (which mocks
Paga entirely on purpose, see test/test_paga.py).

IMPORTANT: this has NOT been run against Paga's real servers by the AI that
wrote it -- that environment's network is restricted to an allowlist that
doesn't include paga.com, so every attempt to reach Paga from there gets
silently intercepted before leaving the sandbox. This script is written
faithfully against Paga's published API docs and is logically sound (the
underlying paga_service functions are unit-tested with mocks), but you are
the first one actually running it against a real Paga server. If something
about the request shape is wrong, this is where you'll find out.

Run this after you've filled in PAGA_PUBLIC_KEY, PAGA_SECRET_KEY, and
PAGA_HASH_KEY in your .env, and before you trust the checkout flow with a
real order.

Usage:
    python -m scripts.verify_paga_credentials

What it does:
    1. Confirms all three Paga env vars are actually set.
    2. Sends a small (₦100) test payment request to Paga's sandbox
       (beta-collect.paga.com -- this never touches real money, and
       PAGA_TEST_MODE should be True while you run this).
    3. Prints exactly what came back, so you can see immediately whether
       the request was accepted (statusCode "0") or rejected, and why.

If this fails, it is almost always one of:
    - PAGA_HASH_KEY does not match what's configured in your Paga
      dashboard (it is a *separate* value from PAGA_SECRET_KEY -- easy to
      mix up)
    - Your business IP is not whitelisted for the Collect API (Paga
      dashboard > Developer Tools > IP Whitelist) -- required even in
      sandbox mode
    - PAGA_TEST_MODE is False while using sandbox-issued keys, or vice versa
"""

import sys

sys.path.insert(0, ".")  # allow running as `python -m scripts.verify_paga_credentials` from repo root

from app.config.settings import get_settings
from app.service import paga_service

settings = get_settings()


def main() -> int:
    print("Checking Paga configuration...\n")

    missing = [
        name
        for name, value in [
            ("PAGA_PUBLIC_KEY", settings.PAGA_PUBLIC_KEY),
            ("PAGA_SECRET_KEY", settings.PAGA_SECRET_KEY),
            ("PAGA_HASH_KEY", settings.PAGA_HASH_KEY),
        ]
        if not value
    ]
    if missing:
        print(f"Missing from .env: {', '.join(missing)}")
        print("Fill these in from your Paga Business dashboard, then re-run this script.")
        return 1

    print(f"PAGA_TEST_MODE:  {settings.PAGA_TEST_MODE}")
    print(f"PAGA_BASE_URL:   {settings.PAGA_BASE_URL}")
    print(f"PAGA_PAYEE_NAME: {settings.PAGA_PAYEE_NAME}")
    if not settings.PAGA_TEST_MODE:
        print("\n*** PAGA_TEST_MODE is False -- this would hit LIVE Paga, not sandbox. ***")
        confirm = input("Type 'yes' to continue anyway, anything else to abort: ")
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            return 1

    print("\nSending a ₦100.00 test payment request to Paga...\n")

    try:
        result = paga_service.create_payment_request(
            reference_number="logson-credential-check",
            amount_kobo=10000,  # ₦100.00
            payer_name="Test Payer",
            payer_email="test@logson.ng",
            callback_url=f"{settings.APP_BASE_URL}/orders/paga/webhook",
        )
    except Exception as exc:  # noqa: BLE001 -- deliberately broad, this is a diagnostic script
        print(f"FAILED: {exc}")
        print(
            "\nIf this mentions a 401 or authentication error, double-check "
            "PAGA_PUBLIC_KEY and PAGA_SECRET_KEY. If it mentions the hash or "
            "signature, double-check PAGA_HASH_KEY specifically -- it's the "
            "single most common thing to get wrong here."
        )
        return 1

    print("SUCCESS -- Paga accepted the request.\n")
    print(f"Reference number:              {result.reference_number}")
    print(f"Web payment link:              {result.web_payment_link}")
    print(f"Bank transfer account number:  {result.bank_transfer_account_number}")
    print(f"USSD short code:               {result.ussd_short_code}")
    print(f"Expires:                       {result.expiry_datetime_utc}")
    print(
        "\nYour credentials and hash signing are working. Note this only "
        "confirms /paymentRequest -- webhook delivery still needs a "
        "publicly reachable APP_BASE_URL to test end-to-end (see README)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())