"""Authentication: phone/OTP login, refresh rotation, and the guards.

These are the security-critical paths, so the tests target the failure modes
rather than the happy path: reuse of a rotated token, brute-forcing a code,
and privilege checks that must hold server-side even when the UI is bypassed.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core import otp_inbox
from app.core.security import create_access_token, normalise_phone
from app.db.models import RefreshToken, User

PREFIX = "/api/v1"
PHONE = "+994501112233"


async def _login_by_phone(client: AsyncClient, phone: str = PHONE) -> str:
    """Complete a phone login and return the access token."""
    otp_inbox.clear()
    response = await client.post(f"{PREFIX}/auth/phone/send-otp", json={"phone": phone})
    assert response.status_code == 200, response.text

    # The console channel records the code, which is what makes the flow
    # demoable and testable without an SMS gateway.
    code = str(otp_inbox.recent()[0]["code"])
    response = await client.post(
        f"{PREFIX}/auth/phone/verify-otp", json={"phone": phone, "code": code}
    )
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


# ---------------------------------------------------------------------------
# Phone / OTP
# ---------------------------------------------------------------------------
async def test_phone_login_creates_a_verified_user(client: AsyncClient) -> None:
    token = await _login_by_phone(client)
    me = await client.get(f"{PREFIX}/users/me", headers={"Authorization": f"Bearer {token}"})
    body = me.json()
    assert body["phone"] == PHONE
    # Completing OTP proves control of the number.
    assert body["phone_verified"] is True
    assert body["role"] == "user"


async def test_otp_is_never_stored_in_plaintext(
    client: AsyncClient, db: tuple[object, async_sessionmaker, str]
) -> None:
    otp_inbox.clear()
    await client.post(f"{PREFIX}/auth/phone/send-otp", json={"phone": PHONE})
    code = str(otp_inbox.recent()[0]["code"])

    _, maker, _ = db
    async with maker() as session:
        from app.db.models import OtpCode

        record = (await session.execute(select(OtpCode))).scalars().first()
    assert record is not None
    assert record.code_hash != code, "the code must be hashed at rest"
    assert len(record.code_hash) == 64


async def test_wrong_code_is_rejected_and_counted(client: AsyncClient) -> None:
    otp_inbox.clear()
    await client.post(f"{PREFIX}/auth/phone/send-otp", json={"phone": PHONE})

    response = await client.post(
        f"{PREFIX}/auth/phone/verify-otp", json={"phone": PHONE, "code": "000000"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "OTP_INVALID"


async def test_otp_locks_out_after_max_attempts(client: AsyncClient) -> None:
    """Without an attempt counter a 6-digit code is brute-forceable in seconds."""
    otp_inbox.clear()
    await client.post(f"{PREFIX}/auth/phone/send-otp", json={"phone": PHONE})

    codes = ["000001", "000002", "000003", "000004", "000005"]
    for wrong in codes:
        await client.post(f"{PREFIX}/auth/phone/verify-otp", json={"phone": PHONE, "code": wrong})

    response = await client.post(
        f"{PREFIX}/auth/phone/verify-otp", json={"phone": PHONE, "code": "000006"}
    )
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "OTP_TOO_MANY_ATTEMPTS"


async def test_resending_invalidates_the_previous_code(client: AsyncClient) -> None:
    otp_inbox.clear()
    await client.post(f"{PREFIX}/auth/phone/send-otp", json={"phone": PHONE})
    first = str(otp_inbox.recent()[0]["code"])

    await client.post(f"{PREFIX}/auth/phone/send-otp", json={"phone": PHONE})

    response = await client.post(
        f"{PREFIX}/auth/phone/verify-otp", json={"phone": PHONE, "code": first}
    )
    assert response.status_code == 400, "an superseded code must not still work"


async def test_send_otp_is_rate_limited_per_phone(client: AsyncClient) -> None:
    """Three per fifteen minutes (plan.md 9.4). Otherwise the endpoint is a
    free SMS cannon pointed at whatever number the caller chooses."""
    for _ in range(3):
        assert (
            await client.post(f"{PREFIX}/auth/phone/send-otp", json={"phone": PHONE})
        ).status_code == 200

    response = await client.post(f"{PREFIX}/auth/phone/send-otp", json={"phone": PHONE})
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+994501112233", "+994501112233"),
        ("994501112233", "+994501112233"),
        ("0501112233", "+994501112233"),
        ("501112233", "+994501112233"),
        ("+994 50 111 22 33", "+994501112233"),
        ("12345", None),
        ("", None),
    ],
)
def test_phone_normalisation(raw: str, expected: str | None) -> None:
    """Without this, 0501234567 and +994501234567 are two accounts for the
    same person and the uniqueness constraint means nothing."""
    assert normalise_phone(raw) == expected


async def test_the_same_number_in_any_format_is_one_account(client: AsyncClient) -> None:
    await _login_by_phone(client, "+994501112233")
    otp_inbox.clear()
    await client.post(f"{PREFIX}/auth/phone/send-otp", json={"phone": "0501112233"})
    code = str(otp_inbox.recent()[0]["code"])
    response = await client.post(
        f"{PREFIX}/auth/phone/verify-otp", json={"phone": "0501112233", "code": code}
    )
    assert response.json()["user"]["phone"] == "+994501112233"


# ---------------------------------------------------------------------------
# Refresh rotation and reuse detection
# ---------------------------------------------------------------------------
async def test_refresh_rotates_the_token(client: AsyncClient) -> None:
    await _login_by_phone(client)
    first_cookie = client.cookies.get("freeshop_refresh")

    response = await client.post(f"{PREFIX}/auth/refresh")
    assert response.status_code == 200
    assert client.cookies.get("freeshop_refresh") != first_cookie, "the token must rotate"


async def test_reusing_a_rotated_token_revokes_the_whole_family(
    client: AsyncClient, db: tuple[object, async_sessionmaker, str]
) -> None:
    """A used token means it leaked: the legitimate holder already rotated it.
    Issuing to both parties would hand the attacker a live session."""
    await _login_by_phone(client)
    stolen = client.cookies.get("freeshop_refresh")
    assert stolen

    await client.post(f"{PREFIX}/auth/refresh")  # legitimate rotation

    client.cookies.set("freeshop_refresh", stolen)
    response = await client.post(f"{PREFIX}/auth/refresh")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "REFRESH_REUSED"

    _, maker, _ = db
    async with maker() as session:
        tokens = list((await session.execute(select(RefreshToken))).scalars())
    assert tokens, "expected refresh tokens to exist"
    assert all(t.revoked_at is not None or t.used_at is not None for t in tokens), (
        "every token in the family must be dead after reuse is detected"
    )


async def test_logout_actually_revokes(client: AsyncClient) -> None:
    await _login_by_phone(client)
    assert (await client.post(f"{PREFIX}/auth/logout")).status_code == 204
    assert (await client.post(f"{PREFIX}/auth/refresh")).status_code == 401


async def test_refresh_without_a_cookie_is_unauthorised(client: AsyncClient) -> None:
    assert (await client.post(f"{PREFIX}/auth/refresh")).status_code == 401


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------
async def test_me_requires_a_token(client: AsyncClient) -> None:
    response = await client.get(f"{PREFIX}/users/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_expired_token_reports_a_distinct_code(client: AsyncClient) -> None:
    """TOKEN_EXPIRED tells the client to refresh; UNAUTHORIZED would send the
    user back to the login screen for no reason."""
    await _login_by_phone(client)
    expired = create_access_token(user_id=1, role="user", phone_verified=True, expires_minutes=-5)
    response = await client.get(
        f"{PREFIX}/users/me", headers={"Authorization": f"Bearer {expired}"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_EXPIRED"


async def test_tampered_token_is_rejected(client: AsyncClient) -> None:
    token = await _login_by_phone(client)
    tampered = token[:-3] + ("aaa" if not token.endswith("aaa") else "bbb")
    response = await client.get(
        f"{PREFIX}/users/me", headers={"Authorization": f"Bearer {tampered}"}
    )
    assert response.status_code == 401


async def test_deactivated_user_loses_access_immediately(
    client: AsyncClient, db: tuple[object, async_sessionmaker, str]
) -> None:
    """The token is still cryptographically valid, so the check must be a
    database read, not a claim."""
    token = await _login_by_phone(client)
    _, maker, _ = db
    async with maker() as session:
        user = (await session.execute(select(User))).scalars().one()
        user.is_active = False
        await session.commit()

    response = await client.get(f"{PREFIX}/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_google_login_without_credentials_is_explicit(client: AsyncClient) -> None:
    """Until GOOGLE_CLIENT_ID exists the endpoint must say so, not 500."""
    response = await client.post(f"{PREFIX}/auth/google", json={"credential": "x" * 32})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "GOOGLE_NOT_CONFIGURED"


async def test_profile_update(client: AsyncClient) -> None:
    token = await _login_by_phone(client)
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.patch(
        f"{PREFIX}/users/me",
        json={"full_name": "Aysel Məmmədova", "preferred_lang": "en"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Aysel Məmmədova"
    assert response.json()["preferred_lang"] == "en"
