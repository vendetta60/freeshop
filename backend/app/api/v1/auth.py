"""Authentication endpoints (plan.md 6.2, 6.3)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Request, Response, status

from app.api.deps import ClientIp, DbSession
from app.config import get_settings
from app.core.errors import AppError, ErrorCode, error_responses
from app.core.security import normalise_phone
from app.schemas.auth import (
    GoogleLoginIn,
    OtpSentOut,
    PhoneIn,
    SessionOut,
    UserOut,
    VerifyOtpIn,
)
from app.services import auth_service, google_service, otp_service

router = APIRouter(prefix="/auth", tags=["auth"], responses=error_responses(401, 404, 422, 429))

REFRESH_COOKIE = "freeshop_refresh"
# Scoped to the auth routes so the token is not attached to every API call -
# it is only ever needed here (plan.md 6.3).
COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.refresh_token_days * 24 * 3600,
        # httpOnly: unreadable from JavaScript, so an XSS bug cannot exfiltrate
        # a long-lived credential.
        httponly=True,
        # Lax rather than Strict: Strict would drop the cookie when a user
        # arrives from an external link, silently logging them out.
        samesite="lax",
        secure=settings.is_production,
        path=COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)


def _session(tokens: auth_service.IssuedTokens) -> SessionOut:
    settings = get_settings()
    return SessionOut(
        access_token=tokens.access,
        expires_in=settings.access_token_minutes * 60,
        user=UserOut.of(tokens.user),
    )


def _require_phone_auth() -> None:
    """404 rather than 403 when the feature is off: a disabled feature should
    not advertise its own existence (plan.md 13, phase 4)."""
    if not get_settings().auth_phone_enabled:
        raise AppError(ErrorCode.NOT_FOUND, status_code=404)


@router.post("/google", summary="Sign in with a Google ID token")
async def google_login(
    payload: GoogleLoginIn,
    session: DbSession,
    response: Response,
    request: Request,
    ip: ClientIp,
) -> SessionOut:
    profile = await google_service.verify_credential(payload.credential)
    user = await auth_service.upsert_google_user(
        session,
        google_id=profile.google_id,
        email=profile.email,
        full_name=profile.full_name,
        picture=profile.picture,
    )
    tokens = await auth_service.issue_tokens(
        session, user, user_agent=request.headers.get("user-agent"), client_ip=ip
    )
    await session.commit()
    _set_refresh_cookie(response, tokens.refresh)
    return _session(tokens)


@router.post("/phone/send-otp", summary="Send a login code")
async def send_login_otp(payload: PhoneIn, session: DbSession, ip: ClientIp) -> OtpSentOut:
    _require_phone_auth()
    settings = get_settings()

    phone = normalise_phone(payload.phone)
    if phone is None:
        raise AppError(ErrorCode.VALIDATION_ERROR, status_code=422, field="phone")

    await otp_service.issue_code(session, phone=phone, purpose="login", client_ip=ip)
    await session.commit()
    return OtpSentOut(
        expires_in=settings.otp_ttl_seconds,
        channel=settings.otp_channel,
        dev_inbox=(settings.is_development or settings.demo_mode)
        and settings.otp_channel == "console",
    )


@router.post("/phone/verify-otp", summary="Verify a login code and sign in")
async def verify_login_otp(
    payload: VerifyOtpIn,
    session: DbSession,
    response: Response,
    request: Request,
    ip: ClientIp,
) -> SessionOut:
    _require_phone_auth()

    phone = normalise_phone(payload.phone)
    if phone is None:
        raise AppError(ErrorCode.VALIDATION_ERROR, status_code=422, field="phone")

    await otp_service.verify_code(session, phone=phone, code=payload.code, purpose="login")
    user = await auth_service.upsert_phone_user(session, phone=phone)
    tokens = await auth_service.issue_tokens(
        session, user, user_agent=request.headers.get("user-agent"), client_ip=ip
    )
    await session.commit()
    _set_refresh_cookie(response, tokens.refresh)
    return _session(tokens)


@router.post("/refresh", summary="Exchange the refresh cookie for a new access token")
async def refresh(
    session: DbSession,
    response: Response,
    request: Request,
    ip: ClientIp,
    freeshop_refresh: Annotated[str | None, Cookie()] = None,
) -> SessionOut:
    if not freeshop_refresh:
        raise AppError(ErrorCode.UNAUTHORIZED, status_code=401)

    try:
        tokens = await auth_service.rotate_tokens(
            session,
            freeshop_refresh,
            user_agent=request.headers.get("user-agent"),
            client_ip=ip,
        )
    except AppError:
        # Commit first: reuse detection revokes the family, and that must
        # persist even though the request itself fails.
        await session.commit()
        _clear_refresh_cookie(response)
        raise

    await session.commit()
    _set_refresh_cookie(response, tokens.refresh)
    return _session(tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Sign out")
async def logout(
    session: DbSession,
    response: Response,
    freeshop_refresh: Annotated[str | None, Cookie()] = None,
) -> None:
    if freeshop_refresh:
        await auth_service.revoke_token(session, freeshop_refresh)
        await session.commit()
    _clear_refresh_cookie(response)
