import logging
import os
import secrets
from functools import lru_cache

from dotenv import load_dotenv

# Loads variables from a .env file in the project root into the process
# environment, if one exists. Safe to call even when no .env is present --
# os.getenv() below just falls back to its defaults in that case.
load_dotenv()

logger = logging.getLogger(__name__)

# The pre-1.0 placeholder that used to be the SECRET_KEY default. Kept only
# so we can positively reject it -- signing real tokens with a value that
# lives in the public repo would let anyone forge a session for any user.
_INSECURE_DEFAULT_SECRET = "dev-secret-change-me-in-production"


def _resolve_secret_key(environment: str) -> str:
    """Resolve the JWT signing key. Accepts either LOGSON_SECRET_KEY (the
    documented name) or SECRET_KEY (the name some existing .env files use),
    so a simple naming mismatch can't silently drop us back onto the public
    placeholder key. In production a real secret is mandatory and its absence
    is fatal; in development we mint a random ephemeral key so local runs and
    the test suite work with zero setup."""
    key = os.getenv("LOGSON_SECRET_KEY") or os.getenv("SECRET_KEY") or ""
    if key and key != _INSECURE_DEFAULT_SECRET:
        return key

    if environment == "production":
        raise RuntimeError(
            "LOGSON_SECRET_KEY (or SECRET_KEY) must be set to a strong random "
            "value in production. Generate one with: "
            'python -c "import secrets; print(secrets.token_hex(32))"'
        )

    logger.warning(
        "No LOGSON_SECRET_KEY/SECRET_KEY set -- using a random ephemeral key "
        "for this process; tokens won't survive a restart. Set one in .env to "
        "silence this warning."
    )
    return secrets.token_hex(32)


def _resolve_cors_origins() -> list[str]:
    """Comma-separated allowed origins. Defaults to the local Vite dev server
    only -- production must set CORS_ORIGINS to the real frontend origin(s).
    Whitespace and empty entries are stripped so 'a, b,' parses cleanly."""
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


class Settings:
    """Single place every other module reads configuration from, instead of
    each file calling os.getenv() on its own."""

    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").lower()

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./logson.db")

    SECRET_KEY: str = _resolve_secret_key(ENVIRONMENT)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))

    # Toggle for the slowapi rate limiter (see app/config/ratelimit.py).
    # Defaults on; the test suite flips it off so the shared app instance
    # doesn't accumulate 429s across many requests.
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"

    # Paga Collect API. Test/live base URLs differ -- PAGA_TEST_MODE picks
    # which one PAGA_BASE_URL resolves to. Get these from your Paga
    # business dashboard (Developer Tools > API Keys).
    PAGA_PUBLIC_KEY: str = os.getenv("PAGA_PUBLIC_KEY", "")
    PAGA_SECRET_KEY: str = os.getenv("PAGA_SECRET_KEY", "")
    # The pre-shared key used to compute the SHA-512 request/webhook hash
    # Paga requires on every call -- separate from PAGA_SECRET_KEY, which
    # is only used for HTTP Basic Auth.
    PAGA_HASH_KEY: str = os.getenv("PAGA_HASH_KEY", "")
    PAGA_TEST_MODE: bool = os.getenv("PAGA_TEST_MODE", "True").lower() == "true"
    PAGA_BASE_URL: str = (
        "https://beta-collect.paga.com" if PAGA_TEST_MODE else "https://collect.paga.com"
    )
    # Shown to the payer as who they're paying. Doesn't have to match your
    # legal business name exactly, just something recognizable.
    PAGA_PAYEE_NAME: str = os.getenv("PAGA_PAYEE_NAME", "Logson")
    # Absolute base URL of this API, used to build the callBackUrl Paga
    # calls once a payment is fulfilled, e.g. https://api.logson.ng ->
    # https://api.logson.ng/orders/paga/webhook. Must be publicly
    # reachable -- localhost will not work here even in dev, since Paga's
    # servers (not your browser) are what call this URL.
    APP_BASE_URL: str = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")

    # Used to verify the ID token Google's Identity Services SDK returns to
    # the frontend. Must match the OAuth client ID configured in Google
    # Cloud Console for this app.
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")

    # SendGrid delivers the "user feedback" emails triggered by
    # POST /feedback. FEEDBACK_NOTIFY_EMAIL is where those land -- defaults
    # to EMAIL_FROM if unset so a single email address is enough to get
    # started.
    SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "noreply@logson.ng")
    FEEDBACK_NOTIFY_EMAIL: str = os.getenv("FEEDBACK_NOTIFY_EMAIL", "") or os.getenv("EMAIL_FROM", "noreply@logson.ng")

    CORS_ORIGINS: list[str] = _resolve_cors_origins()


@lru_cache
def get_settings() -> Settings:
    return Settings()