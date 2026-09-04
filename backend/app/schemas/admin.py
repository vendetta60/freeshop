"""Admin DTOs (plan.md 6.2, 7.2).

Public DTOs resolve `title_az`/`title_en` down to one `title` for the request
language. Admin DTOs deliberately do the opposite and return **both** raw
fields: the panel edits the record, not a rendering of it, and a form that
silently saved the AZ fallback back into the EN column would quietly destroy
the distinction between "no translation" and "translated identically".
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import Category, OrderRequest, Product, User
from app.db.models.setting import DEFAULT_SETTINGS
from app.schemas.catalogue import ImageOut

StockStatus = Literal["available", "out_of_stock", "on_order"]

Slug = Annotated[str, Field(min_length=1, max_length=160, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
class ProductIn(BaseModel):
    """Create payload.

    Only `title_az`, `price_minor` and `category_id` are required. The EN tab
    never blocks a save (plan.md 7.3), and an omitted slug is derived from the
    title, because asking an operator to invent a URL is friction with no
    payoff.
    """

    model_config = ConfigDict(extra="forbid")

    title_az: str = Field(min_length=2, max_length=200)
    title_en: str | None = Field(default=None, max_length=200)
    description_az: str = ""
    description_en: str | None = None
    price_minor: int = Field(ge=0, le=1_000_000_000)
    old_price_minor: int | None = Field(default=None, ge=0, le=1_000_000_000)
    currency: str = Field(default="AZN", min_length=3, max_length=3)
    category_id: int
    stock_status: StockStatus = "available"
    is_featured: bool = False
    slug: Slug | None = None

    city: str | None = Field(default=None, max_length=80)
    district: str | None = Field(default=None, max_length=80)
    transfer_type: Literal["giveaway", "loan"] = "giveaway"
    available_from: datetime | None = None
    available_until: datetime | None = None
    max_borrow_days: int | None = Field(default=None, ge=1, le=365)


class ProductUpdateIn(BaseModel):
    """Patch payload: every field optional, absent means unchanged.

    `title_en`, `description_en` and `old_price_minor` are nullable rather
    than merely optional, so an explicit `null` clears them.
    """

    model_config = ConfigDict(extra="forbid")

    title_az: str | None = Field(default=None, min_length=2, max_length=200)
    title_en: str | None = Field(default=None, max_length=200)
    description_az: str | None = None
    description_en: str | None = None
    price_minor: int | None = Field(default=None, ge=0, le=1_000_000_000)
    old_price_minor: int | None = Field(default=None, ge=0, le=1_000_000_000)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    category_id: int | None = None
    stock_status: StockStatus | None = None
    is_featured: bool | None = None
    slug: Slug | None = None

    city: str | None = Field(default=None, max_length=80)
    district: str | None = Field(default=None, max_length=80)
    transfer_type: Literal["giveaway", "loan"] | None = None
    available_from: datetime | None = None
    available_until: datetime | None = None
    max_borrow_days: int | None = Field(default=None, ge=1, le=365)


class SubmissionIn(BaseModel):
    """What a visitor fills in to offer something.

    Deliberately smaller than `ProductIn`: no slug, no featured flag, no old
    price. Those are the shop-owner's controls, and this is a person giving a
    chair away.

    `price_minor` defaults to 0 - free is the normal case here, not the
    exception (plan.md 0).
    """

    model_config = ConfigDict(extra="forbid")

    title_az: str = Field(min_length=2, max_length=200)
    title_en: str | None = Field(default=None, max_length=200)
    description_az: str = Field(default="", max_length=4000)
    description_en: str | None = Field(default=None, max_length=4000)
    price_minor: int = Field(default=0, ge=0, le=1_000_000_000)
    category_id: int
    stock_status: StockStatus = "available"

    # Where the thing is (FreeShop_Prompt 1). Optional: when it is omitted the
    # service copies the poster's saved default, which is the case that needs
    # to be one click rather than a form.
    city: str | None = Field(default=None, max_length=80)
    district: str | None = Field(default=None, max_length=80)

    # Give away, or lend (FreeShop_Prompt 7). Defaults to the thing this site
    # has always been for.
    transfer_type: Literal["giveaway", "loan"] = "giveaway"
    available_from: datetime | None = None
    available_until: datetime | None = None
    max_borrow_days: int | None = Field(default=None, ge=1, le=365)


class HandoverIn(BaseModel):
    """Which of the people who asked is receiving it (FreeShop_Prompt 5)."""

    model_config = ConfigDict(extra="forbid")

    request_item_id: int


class RequesterOut(BaseModel):
    """One person who asked for a listing, shown ONLY to its owner.

    This is the authorised view Rule F carves out: the public sees a count,
    the giver sees who they are choosing between. Contact details are still
    not here - the giver reaches the person through a conversation, which
    leaves a record and can be reported.
    """

    request_item_id: int
    request_no: str
    user_id: int
    display_name: str
    note: str | None
    quantity: int
    requested_at: datetime


class ModerationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=500)


class MyListingOut(BaseModel):
    """A person's own submission, including why it was turned down."""

    id: int
    slug: str
    title: str
    price_minor: int
    currency: str
    is_free: bool
    category_name: str
    status: str
    moderation_note: str | None
    image: str | None
    is_deleted: bool
    created_at: datetime
    reviewed_at: datetime | None

    transfer_type: str = "giveaway"
    location_label: str | None = None
    # How many people are still waiting on a decision from this owner. It is
    # the badge that makes the handover panel discoverable.
    open_request_count: int = 0

    @classmethod
    def of(cls, product: Product, lang: str = "az", *, open_request_count: int = 0) -> MyListingOut:
        main = product.main_image
        return cls(
            transfer_type=product.transfer_type,
            location_label=product.place_label(),
            open_request_count=open_request_count,
            id=product.id,
            slug=product.slug,
            title=product.title(lang),
            price_minor=product.price_minor,
            currency=product.currency,
            is_free=product.is_free,
            category_name=product.category.name(lang),
            status=product.status,
            moderation_note=product.moderation_note,
            image=main.url if main else None,
            is_deleted=product.is_deleted,
            created_at=product.created_at,
            reviewed_at=product.reviewed_at,
        )


class AdminProductOut(BaseModel):
    id: int
    slug: str
    title_az: str
    title_en: str | None
    description_az: str
    description_en: str | None
    price_minor: int
    old_price_minor: int | None
    currency: str
    category_id: int
    category_name: str
    stock_status: str
    is_featured: bool
    is_deleted: bool
    is_free: bool
    has_en: bool
    status: str
    moderation_note: str | None
    owner_id: int
    owner_name: str | None
    owner_phone: str | None
    reviewed_at: datetime | None
    images: list[ImageOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, product: Product, *, owner_loaded: bool = False) -> AdminProductOut:
        return cls(
            id=product.id,
            slug=product.slug,
            title_az=product.title_az,
            title_en=product.title_en,
            description_az=product.description_az,
            description_en=product.description_en,
            price_minor=product.price_minor,
            old_price_minor=product.old_price_minor,
            currency=product.currency,
            category_id=product.category_id,
            category_name=product.category.name_az,
            stock_status=product.stock_status,
            is_featured=product.is_featured,
            is_deleted=product.is_deleted,
            is_free=product.is_free,
            status=product.status,
            moderation_note=product.moderation_note,
            owner_id=product.owner_id,
            # Loaded only where the relationship was eager-loaded; the queue
            # needs it to know who to thank, the plain table does not.
            owner_name=getattr(product.owner, "full_name", None) if owner_loaded else None,
            owner_phone=getattr(product.owner, "phone", None) if owner_loaded else None,
            reviewed_at=product.reviewed_at,
            # Drives the EN coverage marker in the product table (plan.md 7.3),
            # so gaps are visible at a glance instead of discovered by a
            # visitor browsing in English.
            has_en=bool(product.title_en),
            images=[ImageOut.of(image) for image in product.images],
            created_at=product.created_at,
            updated_at=product.updated_at,
        )


class ImageUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_main: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=100)


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
class CategoryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_az: str = Field(min_length=2, max_length=120)
    name_en: str | None = Field(default=None, max_length=120)
    parent_id: int | None = None
    icon: str | None = Field(default=None, max_length=40)
    sort_order: int = Field(default=0, ge=0, le=999)
    is_active: bool = True
    slug: Slug | None = None


class CategoryUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_az: str | None = Field(default=None, min_length=2, max_length=120)
    name_en: str | None = Field(default=None, max_length=120)
    parent_id: int | None = None
    icon: str | None = Field(default=None, max_length=40)
    sort_order: int | None = Field(default=None, ge=0, le=999)
    is_active: bool | None = None
    slug: Slug | None = None


class AdminCategoryOut(BaseModel):
    id: int
    slug: str
    name_az: str
    name_en: str | None
    parent_id: int | None
    icon: str | None
    sort_order: int
    is_active: bool
    product_count: int = 0

    @classmethod
    def of(cls, category: Category, counts: dict[int, int] | None = None) -> AdminCategoryOut:
        return cls(
            id=category.id,
            slug=category.slug,
            name_az=category.name_az,
            name_en=category.name_en,
            parent_id=category.parent_id,
            icon=category.icon,
            sort_order=category.sort_order,
            is_active=category.is_active,
            product_count=(counts or {}).get(category.id, 0),
        )


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
class AdminUserOut(BaseModel):
    id: int
    email: str | None
    phone: str | None
    phone_verified: bool
    full_name: str | None
    role: str
    is_active: bool
    preferred_lang: str
    last_login_at: datetime | None
    created_at: datetime
    request_count: int = 0

    @classmethod
    def of(cls, user: User, request_count: int = 0) -> AdminUserOut:
        return cls(
            id=user.id,
            email=user.email,
            phone=user.phone,
            phone_verified=user.phone_verified,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            preferred_lang=user.preferred_lang,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            request_count=request_count,
        )


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
class SettingsUpdateIn(BaseModel):
    """A free-form key/value patch, restricted to keys the app actually reads.

    Modelled as one dict rather than 25 optional fields because the key set is
    already declared once, in `DEFAULT_SETTINGS`, and duplicating it here is
    how the two drift apart.
    """

    model_config = ConfigDict(extra="forbid")

    values: dict[str, Any]

    def known(self) -> dict[str, Any]:
        return {k: v for k, v in self.values.items() if k in DEFAULT_SETTINGS}

    def unknown(self) -> list[str]:
        return sorted(k for k in self.values if k not in DEFAULT_SETTINGS)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------
class DayCount(BaseModel):
    date: str
    count: int


class StatsOut(BaseModel):
    products: int
    products_pending: int
    products_deleted: int
    categories: int
    users: int
    requests_total: int
    requests_new: int
    requests_completed: int
    revenue_requested_minor: int
    series: list[DayCount] = Field(default_factory=list)


class AdminRequestSummary(BaseModel):
    """Compact row for the dashboard's recent-requests list."""

    id: int
    request_no: str
    status: str
    total_minor: int
    created_at: datetime

    @classmethod
    def of(cls, request: OrderRequest) -> AdminRequestSummary:
        return cls(
            id=request.id,
            request_no=request.request_no,
            status=request.status,
            total_minor=request.total_minor,
            created_at=request.created_at,
        )
