"""The signed-in user's own profile (plan.md 6.2)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, UploadFile

from app.api.deps import ClientIp, CurrentUser, DbSession
from app.config import get_settings
from app.core.errors import AppError, ErrorCode, error_responses
from app.core.security import normalise_phone
from app.schemas.auth import OtpSentOut, PhoneIn, UpdateMeIn, UserOut, VerifyOtpIn
from app.schemas.location import LocationIn, OwnLocationOut
from app.services import auth_service, geo, image_service, otp_service

router = APIRouter(
    prefix="/users", tags=["users"], responses=error_responses(400, 401, 404, 409, 422)
)


@router.get("/me", summary="Current user")
async def read_me(user: CurrentUser) -> UserOut:
    return UserOut.of(user)


@router.patch("/me", summary="Update your own profile")
async def update_me(payload: UpdateMeIn, user: CurrentUser, session: DbSession) -> UserOut:
    if payload.full_name is not None:
        user.full_name = payload.full_name.strip() or None
    if payload.preferred_lang is not None:
        user.preferred_lang = payload.preferred_lang
    await session.commit()
    return UserOut.of(user)


@router.post("/me/avatar", summary="Replace your avatar")
async def upload_avatar(
    user: CurrentUser,
    session: DbSession,
    file: Annotated[UploadFile, File(description="One image, 5 MB max")],
) -> UserOut:
    """Runs the same pipeline as a product image (plan.md 9.7).

    Deliberately not a separate, lighter path: an avatar is an image uploaded
    by a user, which is exactly the input the sniff-and-re-encode step exists
    for. A second, more relaxed route would be the one that gets exploited.
    """
    settings = get_settings()
    data = await file.read(settings.max_upload_bytes + 1)
    stored = image_service.store(
        data, settings.resolved_upload_dir, max_bytes=settings.max_upload_bytes
    )

    user.avatar_url = f"/static/uploads/{stored.path}"
    await session.commit()
    return UserOut.of(user)


@router.post("/me/phone/send-otp", summary="Send a code to verify a phone number")
async def send_verify_otp(
    payload: PhoneIn, user: CurrentUser, session: DbSession, ip: ClientIp
) -> OtpSentOut:
    settings = get_settings()
    if not settings.auth_phone_enabled:
        raise AppError(ErrorCode.NOT_FOUND, status_code=404)

    phone = normalise_phone(payload.phone)
    if phone is None:
        raise AppError(ErrorCode.VALIDATION_ERROR, status_code=422, field="phone")

    # Claiming a number already verified by someone else would let an attacker
    # take over that account's contact channel.
    existing = await auth_service.get_by_phone(session, phone)
    if existing is not None and existing.id != user.id:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            status_code=409,
            field="phone",
            details={"reason": "already_registered"},
        )

    await otp_service.issue_code(session, phone=phone, purpose="verify_phone", client_ip=ip)
    await session.commit()
    return OtpSentOut(
        expires_in=settings.otp_ttl_seconds,
        channel=settings.otp_channel,
        dev_inbox=(settings.is_development or settings.demo_mode)
        and settings.otp_channel == "console",
    )


@router.post("/me/phone/verify-otp", summary="Confirm the code and attach the number")
async def verify_phone(payload: VerifyOtpIn, user: CurrentUser, session: DbSession) -> UserOut:
    if not get_settings().auth_phone_enabled:
        raise AppError(ErrorCode.NOT_FOUND, status_code=404)

    phone = normalise_phone(payload.phone)
    if phone is None:
        raise AppError(ErrorCode.VALIDATION_ERROR, status_code=422, field="phone")

    await otp_service.verify_code(session, phone=phone, code=payload.code, purpose="verify_phone")
    user.phone = phone
    user.phone_verified = True
    await session.commit()
    return UserOut.of(user)


# ---------------------------------------------------------------------------
# Default location (FreeShop_Prompt 1, 10)
# ---------------------------------------------------------------------------
@router.get("/me/location", summary="Your saved default location")
async def read_my_location(user: CurrentUser) -> OwnLocationOut:
    """Yours, and only yours.

    Even here there are no coordinates in the response - `precision` says
    whether the site resolved your district or only your city, which is the
    part you might want to change. The numbers themselves are a city centroid
    and telling you them would only invite a client to send them back.
    """
    return OwnLocationOut.of_own(user)


@router.put("/me/location", summary="Set or change your default location")
async def set_my_location(
    payload: LocationIn, user: CurrentUser, session: DbSession
) -> OwnLocationOut:
    """Prefills the listing and need forms, and anchors the nearby sort.

    The body carries a PLACE NAME. Coordinates are resolved server-side to
    the centre of that city or district (services/geo.py), so the database
    never learns where anybody actually lives (Rule B).

    An empty city clears the location rather than failing: withdrawing it has
    to be as easy as giving it.
    """
    geo.apply_to(user, payload.model_dump())
    await session.commit()
    return OwnLocationOut.of_own(user)
