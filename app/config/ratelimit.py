"""Application-wide rate limiter (slowapi).

Keyed by client IP so brute-force / credential-stuffing against the auth
routes is throttled per source. On Render (and most PaaS) the app sits behind
a reverse proxy, so ``request.client.host`` is the *proxy's* IP -- every user
would then share a single bucket. We therefore prefer the left-most
``X-Forwarded-For`` entry, which is the original client, and only fall back to
the socket peer when no such header is present (e.g. local dev).

Storage is slowapi's default in-memory backend: counters reset on process
restart and are not shared across instances. That's fine for a single Render
instance; point ``Limiter(storage_uri=...)`` at Redis if this is ever scaled
horizontally.
"""
from slowapi import Limiter
from starlette.requests import Request

from app.config.settings import get_settings

settings = get_settings()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # Left-most entry is the original client; the rest are proxy hops.
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "anonymous"


limiter = Limiter(key_func=_client_ip, enabled=settings.RATE_LIMIT_ENABLED)
