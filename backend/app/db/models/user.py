"""Users, refresh tokens and OTP codes (plan.md 8)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UtcDateTime

if TYPE_CHECKING:
    from app.db.models.cart import CartItem
    from app.db.models.order import OrderRequest
    from app.db.models.product import Product

ROLES = ("admin", "user")
OTP_CHANNELS = ("console", "telegram", "email", "sms")
OTP_PURPOSES = ("login", "verify_phone")


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Either email or phone must be present - enforced by the CheckConstraint
    # below, because a user with neither cannot ever sign in again.
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    google_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)

    full_name: Mapped[str | None] = mapped_column(String(120))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    preferred_lang: Mapped[str] = mapped_column(String(2), default="az", nullable=False)
    role: Mapped[str] = mapped_column(String(10), default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    products: Mapped[list[Product]] = relationship(back_populates="owner")
    cart_items: Mapped[list[CartItem]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    order_requests: Mapped[list[OrderRequest]] = relationship(back_populates="user")

    __table_args__ = (
        CheckConstraint("role IN ('admin','user')", name="role_valid"),
        CheckConstraint("email IS NOT NULL OR phone IS NOT NULL", name="email_or_phone_present"),
    )

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


class RefreshToken(Base, TimestampMixin):
    """Server-side refresh tokens with rotation and reuse detection.

    Stateless refresh tokens cannot be revoked, so logout would not actually
    log anyone out (plan.md D5). The raw token is never stored - only a
    SHA-256 hash, so a database leak does not hand over live sessions.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    # All tokens descended from one login share a family. Presenting an
    # already-used token means it leaked, so the whole family is revoked.
    family_id: Mapped[str] = mapped_column(String(36), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)

    user_agent_hash: Mapped[str | None] = mapped_column(String(64))
    ip_hash: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        Index("ix_refresh_tokens_user_expiry", "user_id", "expires_at"),
        Index("ix_refresh_tokens_family", "family_id"),
    )

    @property
    def is_live(self) -> bool:
        return self.used_at is None and self.revoked_at is None


class OtpCode(Base, TimestampMixin):
    """One-time codes.

    The code itself is hashed: an OTP table storing plaintext codes with no
    attempt counter is brute-forceable in seconds (plan.md D4).
    """

    __tablename__ = "otp_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)

    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(default=5, nullable=False)

    expires_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    ip_hash: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        CheckConstraint("channel IN ('console','telegram','email','sms')", name="channel_valid"),
        CheckConstraint("purpose IN ('login','verify_phone')", name="purpose_valid"),
        Index("ix_otp_lookup", "phone", "purpose", "expires_at"),
    )
