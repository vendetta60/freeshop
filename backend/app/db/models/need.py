"""The reverse side of the board: things people need (FreeShop_Prompt 4).

A listing says "I have this". A need says "I am looking for this". They are
separate tables rather than one table with a direction flag: a need has no
price, no photographs, no stock status and no transfer type, and folding it
into `products` would mean four more nullable columns and a filter on every
existing query - including the ones that already work.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, and_
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import ColumnElement

from app.db.base import Base, TimestampMixin, UtcDateTime
from app.db.models.location import LocationMixin, location_constraints

if TYPE_CHECKING:
    from app.db.models.product import Category
    from app.db.models.user import User

# Lifecycle, owned by the person who posted it.
NEED_STATUSES = ("open", "partially_fulfilled", "fulfilled", "closed", "expired")

# Moderation, owned by the administrator. Mirrors `products.status` exactly,
# so the admin panel reuses its queue, its filters and its vocabulary.
NEED_MODERATION_STATUSES = ("pending", "approved", "rejected")


class NeedRequest(Base, TimestampMixin, LocationMixin):
    __tablename__ = "need_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )

    quantity_needed: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    moderation_status: Mapped[str] = mapped_column(String(10), default="pending", nullable=False)
    moderation_note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    expires_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    # Folded copy, same trick and same function as `products.search_text`, so
    # matching a need against a listing compares like with like
    # (app/core/text.py, app/services/matching.py).
    search_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Set when the need was created from a listing request that went to
    # somebody else (FreeShop_Prompt 5). Kept so the same disappointment never
    # produces two needs, and so the origin is auditable.
    source_order_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("order_request_items.id", ondelete="SET NULL")
    )

    user: Mapped[User] = relationship(back_populates="needs")
    category: Mapped[Category | None] = relationship()

    __table_args__ = (
        CheckConstraint(
            "status IN ('open','partially_fulfilled','fulfilled','closed','expired')",
            name="need_status_valid",
        ),
        CheckConstraint(
            "moderation_status IN ('pending','approved','rejected')",
            name="need_moderation_valid",
        ),
        CheckConstraint("quantity_needed BETWEEN 1 AND 999", name="need_quantity_range"),
        *location_constraints("need"),
        Index("ix_need_requests_public", "moderation_status", "status", "created_at"),
        Index("ix_need_requests_user", "user_id", "created_at"),
        Index("ix_need_requests_category", "category_id", "status"),
        Index("ix_need_requests_geo", "latitude", "longitude"),
    )

    def refresh_search_text(self) -> None:
        from app.core.text import build_search_text

        self.search_text = build_search_text(self.title, self.description)

    @property
    def is_publicly_visible(self) -> bool:
        return self.moderation_status == "approved" and self.status in (
            "open",
            "partially_fulfilled",
        )

    @classmethod
    def public(cls) -> ColumnElement[bool]:
        """The ONE definition of "a visitor may see this need".

        Written once and imported everywhere, for the same reason
        `Product.public()` is: a moderation gate applied in nine places out of
        ten is a leak with good intentions.
        """
        return and_(
            cls.moderation_status == "approved",
            cls.status.in_(("open", "partially_fulfilled")),
        )

    @classmethod
    def open_states(cls) -> ColumnElement[bool]:
        """Still wanted - the states matching treats as live demand."""
        return cls.status.in_(("open", "partially_fulfilled"))
