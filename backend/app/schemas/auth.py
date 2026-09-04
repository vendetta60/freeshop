"""Auth DTOs."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.models import User


class GoogleLoginIn(BaseModel):
    credential: str = Field(min_length=16, description="Google ID token from GIS")


class PhoneIn(BaseModel):
    phone: str = Field(min_length=6, max_length=24)


class VerifyOtpIn(BaseModel):
    phone: str = Field(min_length=6, max_length=24)
    code: str = Field(min_length=4, max_length=8)


class OtpSentOut(BaseModel):
    expires_in: int
    channel: str
    # Only ever true in development, and only for the console channel: it
    # tells the UI to point at /dev/otp-inbox instead of "check your phone".
    dev_inbox: bool = False


class UserOut(BaseModel):
    id: int
    email: str | None
    phone: str | None
    phone_verified: bool
    full_name: str | None
    avatar_url: str | None
    preferred_lang: str
    role: str

    # The saved default location, as a LABEL only (FreeShop_Prompt 1, 15).
    # It ships with the session so the client knows immediately whether the
    # nearby sort will work for this person, without a second request - and
    # so the "add your location" prompt does not flash for someone who
    # already has one. Coordinates are never included.
    location_label: str | None = None
    location_city: str | None = None
    has_location: bool = False

    print("USER IS ADMIN")
    @classmethod
    def of(cls, user: User) -> UserOut:
        return cls(
            id=user.id,
            email=user.email,
            phone=user.phone,
            phone_verified=user.phone_verified,
            full_name=user.full_name,
            avatar_url=user.avatar_url,
            preferred_lang=user.preferred_lang,
            role=user.role,
            location_label=user.place_label(),
            location_city=user.city,
            # Having a NAME is not the same as being placeable: a village the
            # gazetteer does not know gives a label and no coordinates, and
            # the nearby sort needs the coordinates.
            has_location=user.has_coordinates,
        )


class SessionOut(BaseModel):
    """The refresh token is NOT here - it goes out as an httpOnly cookie so
    JavaScript cannot read it, which is the point of storing it that way."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105 - the auth scheme, not a secret
    expires_in: int
    user: UserOut


class UpdateMeIn(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    preferred_lang: str | None = Field(default=None, pattern="^(az|en)$")
