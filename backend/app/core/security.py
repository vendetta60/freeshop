"""Tokens, hashing and phone normalisation (plan.md 6.3, 10)."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt

from app.config import get_settings

ALGORITHM = "HS256"
TokenType = Literal["access"]


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------
def sha256_hex(value: str) -> str:
    """Lookup hash for refresh tokens and OTP codes.

    SHA-256 rather than argon2 on purpose: these are high-entropy random
    values, not user-chosen passwords, so there is nothing to brute-force and
    a deliberately slow hash would only slow down every request.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def constant_time_equals(left: str, right: str) -> bool:
    """Compare digests without leaking their prefix through timing."""
    return hmac.compare_digest(left, right)


def anonymise(value: str | None) -> str | None:
    """One-way hash for IPs and user agents.

    Enough to spot reuse of a leaked token from a new location, without
    keeping the address itself.
    """
    if not value:
        return None
    return sha256_hex(value)[:32]


# ---------------------------------------------------------------------------
# Access tokens
# ---------------------------------------------------------------------------
def create_access_token(
    *, user_id: int, role: str, phone_verified: bool, expires_minutes: int | None = None
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=expires_minutes or settings.access_token_minutes)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "phone_verified": phone_verified,
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


class TokenExpiredError(Exception):
    pass


class TokenInvalidError(Exception):
    pass


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and verify. Raises TokenExpired / TokenInvalid, never returns None."""
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError from exc
    except jwt.InvalidTokenError as exc:
        raise TokenInvalidError from exc
    return payload


# ---------------------------------------------------------------------------
# Refresh tokens
# ---------------------------------------------------------------------------
def new_refresh_token() -> str:
    """256 bits of entropy. Opaque - it carries no claims and means nothing
    without the matching database row, which is what makes revocation work."""
    return secrets.token_urlsafe(32)


def new_family_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# OTP
# ---------------------------------------------------------------------------
def new_otp_code(digits: int = 6) -> str:
    """Cryptographically random, zero-padded so every code is `digits` long."""
    upper = 10**digits
    return str(secrets.randbelow(upper)).zfill(digits)


# ---------------------------------------------------------------------------
# Phone numbers
# ---------------------------------------------------------------------------
_NON_DIGITS = re.compile(r"\D")


def normalise_phone(raw: str) -> str | None:
    """Normalise to E.164 for Azerbaijan, or return None if implausible.

    Without this, `0501234567` and `+994501234567` become two accounts for
    the same person and the uniqueness constraint is meaningless (plan.md 10).

    Accepts: +994501234567, 994501234567, 0501234567, 501234567
    """
    digits = _NON_DIGITS.sub("", raw or "")
    if not digits:
        return None

    if digits.startswith("994"):
        national = digits[3:]
    elif digits.startswith("0"):
        national = digits[1:]
    else:
        national = digits

    # AZ mobile numbers are 9 digits: a 2-digit operator code plus 7.
    if len(national) != 9 or not national.isdigit():
        return None
    return f"+994{national}"
