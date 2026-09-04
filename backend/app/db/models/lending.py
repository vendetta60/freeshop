"""Temporary lending (FreeShop_Prompt 7, Rule D).

A loan is not a gift with a note attached: it has a return date, an owner who
still owns the thing, and a lifecycle that can go wrong. So the lifecycle is
modelled explicitly, on its own table, rather than as a status string bolted
onto the listing.

WHY THE LISTING CARRIES NO `loan_state` COLUMN:
the state of the ladder IS the state of its live loan. Storing it twice means
two rows that can disagree, and the one that disagrees is always the one the
UI reads. `Product.transfer_type` says whether the listing is a loan at all;
everything time-varying is derived from the rows here (services/loan_service).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UtcDateTime

if TYPE_CHECKING:
    from app.db.models.product import Product
    from app.db.models.user import User

# Permanent give-away, or a loan. Every existing listing is a give-away.
TRANSFER_TYPES = ("giveaway", "loan")

# The borrower's side of the story.
#   pending   -> asked, owner has not answered
#   approved  -> owner said yes; the item is reserved, not yet collected
#   borrowed  -> physically handed over
#   returned  -> back with the owner. Terminal.
#   rejected  -> owner said no. Terminal.
#   cancelled -> either party stopped it. Terminal.
LOAN_STATUSES = ("pending", "approved", "borrowed", "returned", "rejected", "cancelled")

# States in which the loan still holds the item, so nobody else may be
# approved for it.
LOAN_ACTIVE_STATUSES = ("approved", "borrowed")
LOAN_TERMINAL_STATUSES = ("returned", "rejected", "cancelled")

# What the listing looks like from outside, derived from the loans above.
LOAN_LISTING_STATES = ("available", "reserved", "borrowed")

# The transitions that are allowed. Anything not listed here is rejected by
# `loan_service.transition` - an explicit table beats a chain of ifs that
# each call site half-remembers.
LOAN_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "pending": ("approved", "rejected", "cancelled"),
    "approved": ("borrowed", "cancelled"),
    "borrowed": ("returned",),
    "returned": (),
    "rejected": (),
    "cancelled": (),
}


class LoanRequest(Base, TimestampMixin):
    __tablename__ = "loan_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    borrower_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    status: Mapped[str] = mapped_column(String(12), default="pending", nullable=False)
    message: Mapped[str | None] = mapped_column(Text)

    # What the borrower asked for, capped by the listing's max_borrow_days.
    requested_days: Mapped[int | None] = mapped_column(Integer)

    approved_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    borrowed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    expected_return_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    returned_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    owner_note: Mapped[str | None] = mapped_column(Text)

    product: Mapped[Product] = relationship(back_populates="loan_requests")
    borrower: Mapped[User] = relationship(back_populates="loan_requests")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','borrowed','returned','rejected','cancelled')",
            name="loan_status_valid",
        ),
        CheckConstraint(
            "requested_days IS NULL OR requested_days BETWEEN 1 AND 365",
            name="loan_days_range",
        ),
        Index("ix_loan_requests_product_status", "product_id", "status"),
        Index("ix_loan_requests_borrower", "borrower_id", "created_at"),
        # The reminder sweep reads exactly this: loans due back soon.
        Index("ix_loan_requests_due", "status", "expected_return_at"),
    )

    @property
    def is_active(self) -> bool:
        return self.status in LOAN_ACTIVE_STATUSES
