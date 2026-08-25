"""One-time codes: issue, verify, rate-limit (plan.md 9.4, D4)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger, mask_phone
from app.core.security import (
    anonymise,
    constant_time_equals,
    new_otp_code,
    sha256_hex,
)
from app.db.models import OtpCode
from app.services.otp_channels import get_channel

log = get_logger(__name__)

# plan.md 9.4. The send limits are configurable (see Settings); these names
# remain as the documented defaults and are what the tests assert against.
MAX_SENDS_PER_PHONE = 3
SEND_WINDOW_MINUTES = 15
MAX_SENDS_PER_IP = 10
IP_WINDOW_MINUTES = 60
MAX_ATTEMPTS = 5


class RateLimitedError(AppError):
    status_code = 429
    code = ErrorCode.RATE_LIMITED


async def _recent_sends(session: AsyncSession, *, phone: str, since: datetime) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(OtpCode)
            .where(OtpCode.phone == phone, OtpCode.created_at >= since)
        )
    ).scalar_one()


async def _recent_sends_from_ip(session: AsyncSession, *, ip_hash: str, since: datetime) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(OtpCode)
            .where(OtpCode.ip_hash == ip_hash, OtpCode.created_at >= since)
        )
    ).scalar_one()


async def issue_code(
    session: AsyncSession,
    *,
    phone: str,
    purpose: str,
    client_ip: str | None = None,
) -> datetime:
    """Create and deliver a code. Returns its expiry.

    Rate limits are enforced per phone AND per IP: per-phone alone is trivially
    bypassed by iterating numbers, which is how you turn an OTP endpoint into
    someone else's SMS bill.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    ip_hash = anonymise(client_ip)

    phone_window = settings.otp_send_window_minutes
    ip_window = settings.otp_ip_window_minutes

    if (
        await _recent_sends(session, phone=phone, since=now - timedelta(minutes=phone_window))
        >= settings.otp_max_sends_per_phone
    ):
        log.warning("otp_rate_limited", scope="phone", phone=mask_phone(phone))
        raise RateLimitedError(details={"scope": "phone", "retry_after_minutes": phone_window})

    if (
        ip_hash
        and await _recent_sends_from_ip(
            session, ip_hash=ip_hash, since=now - timedelta(minutes=ip_window)
        )
        >= settings.otp_max_sends_per_ip
    ):
        log.warning("otp_rate_limited", scope="ip")
        raise RateLimitedError(details={"scope": "ip", "retry_after_minutes": ip_window})

    # Sending a new code invalidates any previous one for the same purpose
    # (plan.md 9.4), so two live codes never exist for one number.
    await session.execute(
        update(OtpCode)
        .where(
            OtpCode.phone == phone,
            OtpCode.purpose == purpose,
            OtpCode.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )

    code = new_otp_code()
    expires_at = now + timedelta(seconds=settings.otp_ttl_seconds)

    session.add(
        OtpCode(
            phone=phone,
            # Hashed, never stored in the clear (plan.md D4).
            code_hash=sha256_hex(code),
            channel=settings.otp_channel,
            purpose=purpose,
            max_attempts=MAX_ATTEMPTS,
            expires_at=expires_at,
            ip_hash=ip_hash,
        )
    )
    await session.flush()

    await get_channel().send(phone=phone, code=code, purpose=purpose, expires_at=expires_at)
    log.info("otp_issued", phone=mask_phone(phone), purpose=purpose, channel=settings.otp_channel)
    return expires_at


async def verify_code(session: AsyncSession, *, phone: str, code: str, purpose: str) -> None:
    """Consume a code, or raise. Never returns a boolean: a caller that
    forgets to check a boolean silently authenticates everyone."""
    now = datetime.now(UTC)

    record = (
        await session.execute(
            select(OtpCode)
            .where(
                OtpCode.phone == phone,
                OtpCode.purpose == purpose,
                OtpCode.consumed_at.is_(None),
            )
            .order_by(OtpCode.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if record is None:
        raise AppError(ErrorCode.OTP_INVALID, status_code=400)

    if record.expires_at <= now:
        raise AppError(ErrorCode.OTP_EXPIRED, status_code=400)

    if record.attempts >= record.max_attempts:
        raise AppError(ErrorCode.OTP_TOO_MANY_ATTEMPTS, status_code=429)

    # Count the attempt and COMMIT it before comparing.
    #
    # A flush alone is not enough: the endpoint raises on a bad code, the
    # request transaction rolls back, and the increment disappears - so the
    # lockout never fires and a six-digit code stays brute-forceable. The
    # counter has to outlive the failure it is counting.
    record.attempts += 1
    await session.commit()
    await session.refresh(record)

    if not constant_time_equals(record.code_hash, sha256_hex(code)):
        remaining = record.max_attempts - record.attempts
        log.info("otp_failed", phone=mask_phone(phone), remaining=remaining)
        raise AppError(ErrorCode.OTP_INVALID, status_code=400, details={"remaining": remaining})

    record.consumed_at = now
    await session.flush()
    log.info("otp_verified", phone=mask_phone(phone), purpose=purpose)
