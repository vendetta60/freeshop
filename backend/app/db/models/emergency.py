"""Admin-verified community aid (FreeShop_Prompt 8, Rule E).

Only an administrator creates one of these. That is the entire point: a badge
reading "Təcili yardım" is a claim about someone's life, and a board where
anyone can apply it to their own post is a board where it stops meaning
anything. The verification happens off the platform; what is recorded here is
that it happened, and by whom.

`verification_note_internal` never leaves the admin API. It is the one field
in the application with that property, so it is stated on the column as well
as in the serializer.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UtcDateTime
from app.db.models.location import LocationMixin, location_constraints

if TYPE_CHECKING:
    from app.db.models.product import Category
    from app.db.models.user import User

CASE_STATUSES = ("draft", "active", "paused", "completed", "cancelled")

# `active` and `paused` are both visible: a paused case tells the community
# that enough has been offered for now, which is information, not noise.
CASE_PUBLIC_STATUSES = ("active", "paused", "completed")

ITEM_PRIORITIES = ("urgent", "normal", "low")

# offered   -> a neighbour said they can bring it
# accepted  -> the admin confirmed it is wanted and expected
# received  -> it arrived. Terminal.
# cancelled -> withdrawn or declined. Terminal.
COMMITMENT_STATUSES = ("offered", "accepted", "received", "cancelled")

COMMITMENT_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "offered": ("accepted", "cancelled"),
    "accepted": ("received", "cancelled"),
    "received": (),
    "cancelled": (),
}


class EmergencyAidCase(Base, TimestampMixin, LocationMixin):
    __tablename__ = "emergency_aid_cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)

    title_az: Mapped[str] = mapped_column(String(200), nullable=False)
    title_en: Mapped[str | None] = mapped_column(String(200))
    description_az: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description_en: Mapped[str | None] = mapped_column(Text)

    # A display name the family agreed to, never their legal identity
    # (Rule F). Nullable, because "a family in Lənkəran" is often the right
    # amount to say.
    beneficiary_display_name: Mapped[str | None] = mapped_column(String(120))

    status: Mapped[str] = mapped_column(String(12), default="draft", nullable=False)

    # ADMIN ONLY. How the situation was verified, who was spoken to, what was
    # seen. Never serialised by a public DTO - see schemas/emergency.py.
    verification_note_internal: Mapped[str | None] = mapped_column(Text)

    created_by_admin_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    published_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    closed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    created_by: Mapped[User] = relationship()
    items: Mapped[list[EmergencyAidItem]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="EmergencyAidItem.sort_order",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','active','paused','completed','cancelled')",
            name="case_status_valid",
        ),
        *location_constraints("case"),
        Index("ix_emergency_cases_public", "status", "published_at"),
    )

    def title(self, lang: str = "az") -> str:
        return (self.title_en or self.title_az) if lang == "en" else self.title_az

    def description(self, lang: str = "az") -> str:
        if lang == "en":
            return self.description_en or self.description_az
        return self.description_az

    @property
    def is_public(self) -> bool:
        return self.status in CASE_PUBLIC_STATUSES

    @property
    def accepts_offers(self) -> bool:
        """A paused case is readable but closed to new offers - that is what
        pausing is for."""
        return self.status == "active"


class EmergencyAidItem(Base, TimestampMixin):
    """One line of what the family needs."""

    __tablename__ = "emergency_aid_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    emergency_case_id: Mapped[int] = mapped_column(
        ForeignKey("emergency_aid_cases.id", ondelete="CASCADE"), index=True
    )

    title_az: Mapped[str] = mapped_column(String(200), nullable=False)
    title_en: Mapped[str | None] = mapped_column(String(200))
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL")
    )

    quantity_needed: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Both are DERIVED from the commitments and recomputed by
    # `emergency_service.recount`. They exist so the public list does not
    # aggregate a second table per row; they are never written by hand.
    quantity_committed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quantity_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    priority: Mapped[str] = mapped_column(String(10), default="normal", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    case: Mapped[EmergencyAidCase] = relationship(back_populates="items")
    category: Mapped[Category | None] = relationship()
    commitments: Mapped[list[AidCommitment]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("priority IN ('urgent','normal','low')", name="aid_priority_valid"),
        CheckConstraint("quantity_needed BETWEEN 1 AND 999", name="aid_quantity_range"),
        Index("ix_aid_items_case_order", "emergency_case_id", "sort_order"),
    )

    def title(self, lang: str = "az") -> str:
        return (self.title_en or self.title_az) if lang == "en" else self.title_az

    @property
    def is_satisfied(self) -> bool:
        return self.quantity_received >= self.quantity_needed


class AidCommitment(Base, TimestampMixin):
    """An offer of one item, not a delivery.

    The distinction matters: marking an item received the moment someone
    clicks would tell the next visitor the family already has blankets that
    are still in a stranger's hallway.
    """

    __tablename__ = "aid_commitments"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("emergency_aid_items.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(10), default="offered", nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

    accepted_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    received_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    item: Mapped[EmergencyAidItem] = relationship(back_populates="commitments")
    user: Mapped[User] = relationship(back_populates="aid_commitments")

    __table_args__ = (
        CheckConstraint(
            "status IN ('offered','accepted','received','cancelled')",
            name="commitment_status_valid",
        ),
        CheckConstraint("quantity BETWEEN 1 AND 999", name="commitment_quantity_range"),
        Index("ix_commitments_item_status", "item_id", "status"),
        Index("ix_commitments_user", "user_id", "created_at"),
    )
