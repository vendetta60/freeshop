"""User lookup and the refresh-token lifecycle (plan.md 6.3, D5)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger, mask_email, mask_phone
from app.core.security import (
    anonymise,
    create_access_token,
    new_family_id,
    new_refresh_token,
    sha256_hex,
)
from app.db.models import RefreshToken, User

log = get_logger(__name__)


class IssuedTokens:
    """Access token for the client, refresh token for the cookie."""

    def __init__(self, access: str, refresh: str, user: User) -> None:
        self.access = access
        self.refresh = refresh
        self.user = user


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
async def get_by_email(session: AsyncSession, email: str) -> User | None:
    return (
        await session.execute(select(User).where(User.email == email.lower()))
    ).scalar_one_or_none()


async def get_by_phone(session: AsyncSession, phone: str) -> User | None:
    return (await session.execute(select(User).where(User.phone == phone))).scalar_one_or_none()


async def upsert_google_user(
    session: AsyncSession, *, google_id: str, email: str, full_name: str | None, picture: str | None
) -> User:
    """Find or create the user behind a verified Google identity.

    Matched on google_id first, then on the verified email - so someone who
    signed up by phone and later uses Google with the same address gets their
    existing account rather than a duplicate.
    """
    email = email.lower()

    user = (
        await session.execute(select(User).where(User.google_id == google_id))
    ).scalar_one_or_none()

    if user is None:
        user = await get_by_email(session, email)
        if user is not None:
            user.google_id = google_id

    if user is None:
        user = User(
            email=email,
            google_id=google_id,
            full_name=full_name,
            avatar_url=picture,
            role="user",
        )
        session.add(user)
        log.info("user_created", via="google", email=mask_email(email))

    # Refresh the profile from Google, but never overwrite a name the user set.
    if picture and not user.avatar_url:
        user.avatar_url = picture
    if full_name and not user.full_name:
        user.full_name = full_name

    user.last_login_at = datetime.now(UTC)
    await session.flush()
    return user


async def upsert_phone_user(session: AsyncSession, *, phone: str) -> User:
    user = await get_by_phone(session, phone)
    if user is None:
        user = User(phone=phone, phone_verified=True, role="user")
        session.add(user)
        log.info("user_created", via="phone", phone=mask_phone(phone))
    else:
        # Reaching here means they proved control of the number.
        user.phone_verified = True

    user.last_login_at = datetime.now(UTC)
    await session.flush()
    return user


# ---------------------------------------------------------------------------
# Refresh tokens
# ---------------------------------------------------------------------------
async def issue_tokens(
    session: AsyncSession,
    user: User,
    *,
    family_id: str | None = None,
    user_agent: str | None = None,
    client_ip: str | None = None,
) -> IssuedTokens:
    settings = get_settings()
    raw = new_refresh_token()

    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=sha256_hex(raw),
            family_id=family_id or new_family_id(),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
            user_agent_hash=anonymise(user_agent),
            ip_hash=anonymise(client_ip),
        )
    )
    await session.flush()

    access = create_access_token(
        user_id=user.id, role=user.role, phone_verified=user.phone_verified
    )
    return IssuedTokens(access=access, refresh=raw, user=user)


async def rotate_tokens(
    session: AsyncSession,
    raw_refresh: str,
    *,
    user_agent: str | None = None,
    client_ip: str | None = None,
) -> IssuedTokens:
    """Exchange a refresh token for a new pair, with reuse detection.

    A token that has already been used means it leaked - the legitimate holder
    rotated it, so whoever is presenting the old one copied it. The response
    is to revoke the entire family, forcing a fresh login, rather than to
    quietly issue tokens to both parties (plan.md 6.3).
    """
    now = datetime.now(UTC)
    record = (
        await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == sha256_hex(raw_refresh))
        )
    ).scalar_one_or_none()

    if record is None:
        raise AppError(ErrorCode.TOKEN_INVALID, status_code=401)

    if record.used_at is not None or record.revoked_at is not None:
        await revoke_family(session, record.family_id)
        log.warning("refresh_reuse_detected", user_id=record.user_id, family=record.family_id)
        raise AppError(ErrorCode.REFRESH_REUSED, status_code=401)

    if record.expires_at <= now:
        raise AppError(ErrorCode.TOKEN_EXPIRED, status_code=401)

    user = (
        await session.execute(select(User).where(User.id == record.user_id))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise AppError(ErrorCode.TOKEN_INVALID, status_code=401)

    record.used_at = now
    await session.flush()

    return await issue_tokens(
        session,
        user,
        family_id=record.family_id,
        user_agent=user_agent,
        client_ip=client_ip,
    )


async def revoke_family(session: AsyncSession, family_id: str) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    await session.flush()


async def revoke_token(session: AsyncSession, raw_refresh: str) -> None:
    """Logout. Revokes the whole family so every device from that login is
    signed out, which is what people expect 'log out' to mean."""
    record = (
        await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == sha256_hex(raw_refresh))
        )
    ).scalar_one_or_none()
    if record is not None:
        await revoke_family(session, record.family_id)
