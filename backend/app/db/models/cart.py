"""Cart lines (plan.md 8)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.product import Product
    from app.db.models.user import User


class CartItem(Base, TimestampMixin):
    __tablename__ = "cart_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    user: Mapped[User] = relationship(back_populates="cart_items")
    product: Mapped[Product] = relationship()

    __table_args__ = (
        # Adding a product already in the cart increments it; it never creates
        # a second line. The constraint makes that a database guarantee rather
        # than an application convention.
        UniqueConstraint("user_id", "product_id", name="uq_cart_user_product"),
        CheckConstraint("quantity BETWEEN 1 AND 99", name="quantity_in_range"),
    )
