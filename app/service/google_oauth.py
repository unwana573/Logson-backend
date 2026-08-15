from dataclasses import dataclass

from fastapi import HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.config.settings import get_settings

settings = get_settings()


@dataclass
class GoogleProfile:
    google_id: str
    email: str
    full_name: str


def verify_google_id_token(token: str) -> GoogleProfile:
    """Verifies a Google Identity Services ID token and returns the
    profile fields we care about. Isolated in its own function so tests can
    monkeypatch this instead of hitting Google's servers."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID is not configured on the server")

    try:
        payload = google_id_token.verify_oauth2_token(
            token, google_requests.Request(), settings.GOOGLE_CLIENT_ID
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    if not payload.get("email_verified", False):
        raise HTTPException(status_code=401, detail="Google account email is not verified")

    return GoogleProfile(
        google_id=payload["sub"],
        email=payload["email"],
        full_name=payload.get("name") or payload.get("email").split("@")[0],
    )
