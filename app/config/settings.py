import os
from functools import lru_cache

from dotenv import load_dotenv

# Loads variables from a .env file in the project root into the process
# environment, if one exists. Safe to call even when no .env is present --
# os.getenv() below just falls back to its defaults in that case.
load_dotenv()


class Settings:
    """Single place every other module reads configuration from, instead of
    each file calling os.getenv() on its own."""

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./logson.db")

    SECRET_KEY: str = os.getenv("LOGSON_SECRET_KEY", "dev-secret-change-me-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    PAYSTACK_SECRET_KEY: str = os.getenv("PAYSTACK_SECRET_KEY", "")
    PAYSTACK_BASE_URL: str = "https://api.paystack.co"

    # Used to verify the ID token Google's Identity Services SDK returns to
    # the frontend. Must match the OAuth client ID configured in Google
    # Cloud Console for this app.
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")

    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")


@lru_cache
def get_settings() -> Settings:
    return Settings()
