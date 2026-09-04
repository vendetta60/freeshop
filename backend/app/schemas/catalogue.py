"""Public catalogue DTOs (plan.md 6.1).

Bilingual fields are resolved to a single value here rather than shipped as
`title_az` + `title_en`: the client should never have to know which language
a field came from, and the AZ fallback (plan.md 7.3) belongs on the server.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import Category, Product, ProductImage
from app.schemas.location import LocationOut

Lang = Literal["az", "en"]

# `nearby` and `most_requested` are new (FreeShop_Prompt 2). Both degrade to
# `newest` rather than failing when the data they need is missing - no
# location, no requests - which is what keeps the page working for a visitor
# who has told the site nothing about themselves.
SortKey = Literal[
    "newest",
    "oldest",
    "price_asc",
    "price_desc",
    "relevance",
    "nearby",
    "most_requested",
]

TransferType = Literal["giveaway", "loan"]
LoanListingState = Literal["available", "reserved", "borrowed"]


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    per_page: int
    pages: int
    # Which sort the server ACTUALLY used. It differs from the requested one
    # when `nearby` was asked for with nothing to measure from - the page
    # still renders, and this is how the client knows to offer "add your
    # location for better results" (FreeShop_Prompt 2).
    applied_sort: str | None = None


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

    # --- location and lending (FreeShop_Prompt 1, 7) ------------------------
    location: LocationOut
    transfer_type: TransferType = "giveaway"
    # Only meaningful for a loan listing; `available` for a give-away.
    loan_state: LoanListingState = "available"

    @classmethod
    def of(
        cls,
        product: Product,
        lang: Lang,
        *,
        distance_km: float | None = None,
        loan_state: str = "available",
    ) -> ProductCardOut:
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
            location=LocationOut.of(product, distance_km),
            transfer_type=cast("TransferType", product.transfer_type),
            loan_state=cast("LoanListingState", loan_state),
        )


class ProductDetailOut(ProductCardOut):
    description: str
    images: list[ImageOut] = Field(default_factory=list)
    created_at: datetime

    # Loan terms. Null on a give-away, which is every listing that existed
    # before lending was added.
    available_from: datetime | None = None
    available_until: datetime | None = None
    max_borrow_days: int | None = None

    # How many people have asked and not yet been answered. A count, never a
    # list of names (Rule F) - the giver sees the people through the handover
    # panel, which is an authorised view; a visitor sees only the number.
    open_request_count: int = 0

    @classmethod
    def of(
        cls,
        product: Product,
        lang: Lang,
        *,
        distance_km: float | None = None,
        loan_state: str = "available",
        open_request_count: int = 0,
    ) -> ProductDetailOut:
        card = ProductCardOut.of(product, lang, distance_km=distance_km, loan_state=loan_state)
        return cls(
            **card.model_dump(),
            description=product.description(lang),
            images=[ImageOut.of(image) for image in product.images],
            created_at=product.created_at,
            available_from=product.available_from,
            available_until=product.available_until,
            max_borrow_days=product.max_borrow_days,
            open_request_count=open_request_count,
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
