"""Order requests and their line snapshots (plan.md 8, 9.1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.product import Product
    from app.db.models.user import User

ORDER_STATUSES = ("new", "viewed", "completed", "cancelled")


class OrderRequest(Base, TimestampMixin):
    """A contact request, NOT an order.

    Nothing is charged. Submitting produces this record and shows the buyer
    the seller's contact channels (plan.md 4.3).
    """

    __tablename__ = "order_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Human-readable, so the admin can quote it on the phone: SR-2026-0041.
    request_no: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(12), default="new", nullable=False)

    contact_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(255))
    note: Mapped[str | None] = mapped_column(Text)
    admin_note: Mapped[str | None] = mapped_column(Text)

    # Denormalised so the admin list does not need to sum lines per row.
    total_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Idempotency (plan.md 6.1): a repeat submission within ten minutes returns
    # the original request instead of creating a duplicate. Nullable because
    # older rows and non-idempotent callers have none.
    idempotency_key: Mapped[str | None] = mapped_column(String(64))

    user: Mapped[User] = relationship(back_populates="order_requests")
    items: Mapped[list[OrderRequestItem]] = relationship(
        back_populates="order_request", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("status IN ('new','viewed','completed','cancelled')", name="status_valid"),
        Index("ix_order_requests_status", "status", "created_at"),
        Index("ix_order_requests_user", "user_id", "created_at"),
        Index("ix_order_requests_idempotency", "user_id", "idempotency_key"),
    )


class OrderRequestItem(Base, TimestampMixin):
    """A snapshot, not a live reference.

    Title and price are copied at submission time so the request stays
    truthful after the product is renamed, repriced, or soft-deleted
    (plan.md 9.1, 9.6). `product_id` is SET NULL rather than CASCADE for the
    same reason: losing the product must not lose the history.
    """

    __tablename__ = "order_request_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_request_id: Mapped[int] = mapped_column(
        ForeignKey("order_requests.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))

    title_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price_at_request_minor: Mapped[int] = mapped_column(Integer, nullable=False)

    order_request: Mapped[OrderRequest] = relationship(back_populates="items")
    product: Mapped[Product | None] = relationship()

    __table_args__ = (CheckConstraint("quantity >= 1", name="quantity_positive"),)
