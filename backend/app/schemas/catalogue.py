"""Public catalogue DTOs (plan.md 6.1).

Bilingual fields are resolved to a single value here rather than shipped as
`title_az` + `title_en`: the client should never have to know which language
a field came from, and the AZ fallback (plan.md 7.3) belongs on the server.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import Category, Product, ProductImage

Lang = Literal["az", "en"]
SortKey = Literal["newest", "oldest", "price_asc", "price_desc", "relevance"]


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    per_page: int
    pages: int


class ImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    width: int | None = None
    height: int | None = None
    is_main: bool

    @classmethod
    def of(cls, image: ProductImage) -> ImageOut:
        return cls(
            id=image.id,
            url=image.url,
            width=image.width,
            height=image.height,
            is_main=image.is_main,
        )


class CategoryOut(BaseModel):
    id: int
    slug: str
    name: str
    parent_id: int | None = None
    children: list[CategoryOut] = Field(default_factory=list)
    product_count: int = 0

    @classmethod
    def of(
        cls, category: Category, lang: Lang, counts: dict[int, int] | None = None
    ) -> CategoryOut:
        counts = counts or {}
        return cls(
            id=category.id,
            slug=category.slug,
            name=category.name(lang),
            parent_id=category.parent_id,
            children=[
                cls.of(child, lang, counts)
                for child in sorted(category.children, key=lambda c: c.sort_order)
                if child.is_active
            ],
            product_count=counts.get(category.id, 0),
        )


class ProductCardOut(BaseModel):
    """The shape the grid needs - deliberately smaller than the detail DTO."""

    id: int
    slug: str
    title: str
    price_minor: int
    old_price_minor: int | None = None
    currency: str
    stock_status: str
    category_id: int
    category_name: str
    image: str | None = None
    image_width: int | None = None
    image_height: int | None = None
    is_featured: bool

    @classmethod
    def of(cls, product: Product, lang: Lang) -> ProductCardOut:
        main = product.main_image
        return cls(
            id=product.id,
            slug=product.slug,
            title=product.title(lang),
            price_minor=product.price_minor,
            old_price_minor=product.old_price_minor,
            currency=product.currency,
            stock_status=product.stock_status,
            category_id=product.category_id,
            category_name=product.category.name(lang),
            image=main.url if main else None,
            image_width=main.width if main else None,
            image_height=main.height if main else None,
            is_featured=product.is_featured,
        )


class ProductDetailOut(ProductCardOut):
    description: str
    images: list[ImageOut] = Field(default_factory=list)
    created_at: datetime

    @classmethod
    def of(cls, product: Product, lang: Lang) -> ProductDetailOut:
        card = ProductCardOut.of(product, lang)
        return cls(
            **card.model_dump(),
            description=product.description(lang),
            images=[ImageOut.of(image) for image in product.images],
            created_at=product.created_at,
        )


class ContactOut(BaseModel):
    """Seller contact channels - the entire payoff of the request flow."""

    phone: str
    whatsapp: str
    telegram: str
    email: str
    address: str
    working_hours: str
    socials: dict[str, str] = Field(default_factory=dict)
