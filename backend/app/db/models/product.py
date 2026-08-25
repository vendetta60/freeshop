"""Categories, products and product images (plan.md 8)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    and_,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import ColumnElement

from app.db.base import Base, TimestampMixin, UtcDateTime

if TYPE_CHECKING:
    from app.db.models.user import User

STOCK_STATUSES = ("available", "out_of_stock", "on_order")

# Moderation states. Anyone signed in may offer an item; an administrator
# decides whether it appears on the site.
MODERATION_STATUSES = ("pending", "approved", "rejected")


class Category(Base, TimestampMixin):
    """Exactly two levels: parent -> child. No deeper (plan.md D11).

    Unbounded depth is a UX and query trap; the nav design depends on the
    depth being known, and the service layer rejects a third level.
    """

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)

    # *_az is required; *_en is optional and falls back to *_az at
    # serialisation time, so EN is never blocked on a missing translation
    # (plan.md 7.3).
    name_az: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(120))

    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), index=True
    )
    icon: Mapped[str | None] = mapped_column(String(40))
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    parent: Mapped[Category | None] = relationship(
        remote_side="Category.id", back_populates="children"
    )
    children: Mapped[list[Category]] = relationship(back_populates="parent")
    products: Mapped[list[Product]] = relationship(back_populates="category")

    __table_args__ = (Index("ix_categories_parent_sort", "parent_id", "sort_order"),)

    def name(self, lang: str = "az") -> str:
        return (self.name_en or self.name_az) if lang == "en" else self.name_az


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)

    title_az: Mapped[str] = mapped_column(String(200), nullable=False)
    title_en: Mapped[str | None] = mapped_column(String(200))
    description_az: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description_en: Mapped[str | None] = mapped_column(Text)

    # INTEGER minor units (qepik), never a float (plan.md 8). Floating-point
    # money is how totals end up off by a penny.
    price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    old_price_minor: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="AZN", nullable=False)

    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    stock_status: Mapped[str] = mapped_column(String(16), default="available", nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    view_count: Mapped[int] = mapped_column(default=0, nullable=False)

    # Diacritic-folded copy of every searchable field. Azerbaijani is usually
    # typed without diacritics, and SQLite LIKE cannot fold ə -> e, so the
    # folded text is stored and matched instead (app/core/text.py).
    search_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Moderation (plan.md D25). Defaults to `pending` deliberately: a listing
    # is invisible until someone approves it, so a new code path that forgets
    # to set this fails CLOSED - nothing reaches the site by accident.
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False, index=True)
    moderation_note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    # Soft delete: hard-deleting orphans historical order requests (plan.md D7).
    deleted_at: Mapped[datetime | None] = mapped_column(UtcDateTime, index=True)

    category: Mapped[Category] = relationship(back_populates="products")
    owner: Mapped[User] = relationship(back_populates="products")
    images: Mapped[list[ProductImage]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductImage.sort_order",
    )

    __table_args__ = (
        CheckConstraint(
            "stock_status IN ('available','out_of_stock','on_order')", name="stock_valid"
        ),
        CheckConstraint("price_minor >= 0", name="price_non_negative"),
        CheckConstraint("status IN ('pending','approved','rejected')", name="moderation_valid"),
        Index("ix_products_listing", "category_id", "deleted_at", "created_at"),
        Index("ix_products_price", "deleted_at", "price_minor"),
        Index("ix_products_featured", "is_featured", "deleted_at"),
        Index("ix_products_moderation", "status", "created_at"),
        Index("ix_products_search", "search_text"),
    )

    def refresh_search_text(self) -> None:
        """Recompute the folded search copy. Call after any title/description
        change - a stale search index is worse than none, because it fails
        silently."""
        from app.core.text import build_search_text

        self.search_text = build_search_text(
            self.title_az, self.title_en, self.description_az, self.description_en
        )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def is_free(self) -> bool:
        """Zero is a price, not a missing one: the point of the site is that
        most things are given away (plan.md 0)."""
        return self.price_minor == 0

    @property
    def is_publicly_visible(self) -> bool:
        """The in-Python mirror of `public()`, for objects already loaded."""
        return self.deleted_at is None and self.status == "approved"

    @classmethod
    def public(cls) -> ColumnElement[bool]:
        """The ONE definition of "a visitor may see this".

        Approved AND not deleted. Written once and imported everywhere,
        because a moderation gate applied in nine places out of ten is not a
        moderation gate - it is a leak with good intentions.
        """
        return and_(cls.deleted_at.is_(None), cls.status == "approved")

    def title(self, lang: str = "az") -> str:
        return (self.title_en or self.title_az) if lang == "en" else self.title_az

    def description(self, lang: str = "az") -> str:
        if lang == "en":
            return self.description_en or self.description_az
        return self.description_az

    @property
    def main_image(self) -> ProductImage | None:
        for image in self.images:
            if image.is_main:
                return image
        return self.images[0] if self.images else None


class ProductImage(Base, TimestampMixin):
    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )

    # Either a repo-relative path ('products/a3/a3f9c2.jpg') or an absolute
    # URL. The seed uses absolute URLs for demo photography; uploads from the
    # admin panel are always local. `is_remote` tells the serializer which.
    path: Mapped[str] = mapped_column(String(600), nullable=False)

    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    blurhash: Mapped[str | None] = mapped_column(String(60))

    is_main: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)

    product: Mapped[Product] = relationship(back_populates="images")

    __table_args__ = (Index("ix_product_images_order", "product_id", "sort_order"),)

    @property
    def is_remote(self) -> bool:
        return self.path.startswith(("http://", "https://"))

    @property
    def url(self) -> str:
        return self.path if self.is_remote else f"/static/uploads/{self.path}"
