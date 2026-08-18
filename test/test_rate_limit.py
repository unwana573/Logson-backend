"""The auth routes are rate-limited per client IP (see app/config/ratelimit.py).

The shared test app has the limiter disabled by the `client` fixture, so this
test opts back in and uses a dedicated X-Forwarded-For value: that keeps its
per-IP bucket isolated from every other test and from re-runs.
"""
from app.config.ratelimit import limiter


def test_login_is_rate_limited(client):
    limiter.enabled = True
    try:
        headers = {"X-Forwarded-For": "203.0.113.77"}  # unique client bucket
        statuses = [
            client.post(
                "/auth/login",
                json={"email": "nobody@logson.ng", "password": "whatever1"},
                headers=headers,
            ).status_code
            for _ in range(12)
        ]
    finally:
        limiter.enabled = False

    # login is capped at 10/minute: the first 10 get the normal auth rejection,
    # then the limiter kicks in with 429 Too Many Requests.
    assert all(s in (400, 401) for s in statuses[:10])
    assert statuses[10] == 429
    assert statuses[11] == 429
