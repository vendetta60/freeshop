"""Shared request dependencies and the authorisation guards."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.core.i18n import normalise_lang
from app.core.security import TokenExpiredError, TokenInvalidError, decode_access_token
from app.db.models import User
from app.db.session import get_session

DbSession = Annotated[AsyncSession, Depends(get_session)]


async def get_lang(
    lang: Annotated[str | None, Query(description="az | en, overrides Accept-Language")] = None,
    accept_language: Annotated[str | None, Header()] = None,
) -> str:
    """Resolve the response language: ?lang= wins, then Accept-Language, then az."""
    if lang in ("az", "en"):
        return lang
    return normalise_lang(accept_language)


Lang = Annotated[str, Depends(get_lang)]


def client_ip(request: Request) -> str | None:
    """Behind Caddy the socket address is the proxy, so prefer X-Real-IP."""
    forwarded = request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


ClientIp = Annotated[str | None, Depends(client_ip)]


async def _user_from_bearer(request: Request, session: AsyncSession) -> User | None:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None

    token = header[7:].strip()
    try:
        payload = decode_access_token(token)
    except TokenExpiredError as exc:
        # A distinct code, so the client knows to refresh rather than to
        # bounce the user to the login screen.
        raise AppError(ErrorCode.TOKEN_EXPIRED, status_code=401) from exc
    except TokenInvalidError as exc:
        raise AppError(ErrorCode.TOKEN_INVALID, status_code=401) from exc

    user = (
        await session.execute(select(User).where(User.id == int(payload["sub"])))
    ).scalar_one_or_none()

    # Re-read the user rather than trusting the token's claims: a deactivated
    # account must lose access immediately, not when its token expires.
    if user is None or not user.is_active:
        raise AppError(ErrorCode.TOKEN_INVALID, status_code=401)
    return user


async def get_current_user(request: Request, session: DbSession) -> User:
    user = await _user_from_bearer(request, session)
    if user is None:
        raise AppError(ErrorCode.UNAUTHORIZED, status_code=401)
    return user


async def get_optional_user(request: Request, session: DbSession) -> User | None:
    """For endpoints that behave differently when signed in but do not require it."""
    try:
        return await _user_from_bearer(request, session)
    except AppError:
        return None


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated["User | None", Depends(get_optional_user)]


async def require_admin(user: CurrentUser) -> User:
    """Server-side role check. Frontend route guards are UX, not security -
    assume they are bypassed (plan.md 10)."""
    if not user.is_admin:
        raise AppError(ErrorCode.FORBIDDEN, status_code=403)
    return user


AdminUser = Annotated[User, Depends(require_admin)]


async def require_phone_verified(user: CurrentUser) -> User:
    """Gate on publishing a product (plan.md 9.3).

    Returns a distinct code so the frontend can open the verify modal instead
    of showing a generic 'forbidden'.
    """
    if not user.phone_verified:
        raise AppError(ErrorCode.PHONE_NOT_VERIFIED, status_code=403)
    return user


VerifiedUser = Annotated[User, Depends(require_phone_verified)]
