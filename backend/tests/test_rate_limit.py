"""Rate limits and the body-size cap (plan.md 10).

The limiter is the one piece of middleware that can take the whole site down
if it is wrong, so these check both directions: that it fires, and that it
does not fire on the things that must never be limited.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.rate_limit import MAX_BODY_BYTES, RateLimitMiddleware
from tests.conftest import build_client

PREFIX = "/api/v1"


@pytest.fixture
async def limited(
    db: tuple[AsyncEngine, async_sessionmaker, str], monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncClient]:
    """A client whose app carries the limiter.

    Every test app is built with `env=development`, so the middleware is
    already in the stack for the whole suite - counters are per app instance,
    and no other test comes close to a bucket. This fixture exists to make
    that explicit for the tests that deliberately do.
    """
    async with build_client(db, monkeypatch) as client:
        yield client


async def test_the_auth_bucket_fires_and_returns_the_normal_envelope(limited: AsyncClient) -> None:
    """20 per minute on /auth/* (plan.md 10).

    Driven through `/auth/google` rather than `send-otp`: the OTP service has
    its own, tighter per-phone limit (plan.md 9.4) which would fire first, and
    this test is about the middleware. Google is unconfigured here, so each
    call is a cheap 400 with no side effects.
    """
    last = None
    for _ in range(25):
        last = await limited.post(f"{PREFIX}/auth/google", json={"credential": "x"})
        if last.status_code == 429:
            break

    assert last is not None
    assert last.status_code == 429
    # Same shape as every other error, so the client needs no special case.
    assert last.json()["error"]["code"] == "RATE_LIMITED"
    assert last.headers["retry-after"].isdigit()
    assert last.headers["cache-control"] == "no-store"


async def test_health_probes_are_never_limited(limited: AsyncClient) -> None:
    """A limiter that takes out readiness turns a spike into an outage."""
    for _ in range(60):
        response = await limited.get(f"{PREFIX}/healthz")
        assert response.status_code == 200


async def test_the_catalogue_is_not_limited_by_the_auth_bucket(limited: AsyncClient) -> None:
    """Browsing has to stay comfortable: 25 catalogue reads is a normal
    session, and the tight bucket must not apply to it."""
    for _ in range(25):
        assert (await limited.get(f"{PREFIX}/products")).status_code == 200


async def test_an_oversized_body_is_refused_before_it_is_read(limited: AsyncClient) -> None:
    response = await limited.post(
        f"{PREFIX}/order-requests",
        json={"contact_phone": "+994501112233"},
        headers={"content-length": str(MAX_BODY_BYTES + 1)},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_the_most_specific_rule_wins() -> None:
    """Rule order is the whole correctness of the table: a global prefix that
    matched first would make every specific bucket dead code."""
    assert RateLimitMiddleware._rule("/api/v1/auth/phone/send-otp")[1] == 20
    # Refresh is the boot path for every visitor, not a credential attempt.
    assert RateLimitMiddleware._rule("/api/v1/auth/refresh")[1] == 300
    assert RateLimitMiddleware._rule("/api/v1/users/me/avatar")[1] == 30
    assert RateLimitMiddleware._rule("/api/v1/products")[1] == 300

    # Uploads are throttled; READING the admin tables is not. The first
    # version of this table used the `/admin/products` prefix for the upload
    # bucket and throttled the whole panel to sixty requests an hour.
    assert RateLimitMiddleware._rule("/api/v1/admin/products/7/images")[1] == 60
    assert RateLimitMiddleware._rule("/api/v1/products/7/images")[1] == 60
    assert RateLimitMiddleware._rule("/api/v1/admin/products")[1] == 300
    assert RateLimitMiddleware._rule("/api/v1/admin/products/7")[1] == 300


def test_the_window_slides() -> None:
    limiter = RateLimitMiddleware(app=object())
    key = ("test", "1.2.3.4")

    for _ in range(3):
        assert limiter._too_many(key, limit=3, window=60) is None

    retry = limiter._too_many(key, limit=3, window=60)
    assert retry is not None and 0 < retry <= 60

    # Age the recorded hits out of the window rather than sleeping through it.
    limiter._hits[key] = type(limiter._hits[key])(x - 61 for x in limiter._hits[key])
    assert limiter._too_many(key, limit=3, window=60) is None


async def test_refreshing_a_session_is_not_credential_hammering(limited: AsyncClient) -> None:
    """Every page load calls `/auth/refresh` once. Thirty loads in a minute is
    a person browsing, not an attack - and the interaction suite proved it by
    being signed out mid-run when this shared the sign-in bucket."""
    for _ in range(30):
        response = await limited.post(f"{PREFIX}/auth/refresh")
        assert response.status_code != 429
