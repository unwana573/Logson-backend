from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config.settings import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Longer-lived token whose only job is to mint new access tokens via
    POST /auth/refresh, without asking the person to log in again every
    ACCESS_TOKEN_EXPIRE_MINUTES. The "type" claim is what stops a refresh
    token from being used directly as an access token, or vice versa."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str, expected_type: str) -> Optional[dict]:
    """Decodes a token and enforces its "type" claim matches what the
    caller expects, so a leaked refresh token can't be replayed as an
    access token against a normal authenticated route, and vice versa."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None

    if payload.get("type") != expected_type:
        return None
    return payload


def decode_access_token(token: str) -> Optional[dict]:
    return decode_token(token, expected_type="access")


def decode_refresh_token(token: str) -> Optional[dict]:
    return decode_token(token, expected_type="refresh")