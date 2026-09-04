"""Catalogue writes: products, categories and product images (plan.md 6.2, 9.5-9.7).

The read side lives in the public routers; everything that mutates the
catalogue is here, because the invariants - slug uniqueness, two-level
categories, exactly one main image, soft delete - are properties of the
catalogue rather than of any one endpoint.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError, ErrorCode, NotFoundError
from app.core.text import slugify
from app.db.models import Category, OrderRequestItem, Product, ProductImage, User
from app.services import geo

PRODUCT_RELATIONS = (
    selectinload(Product.images),
    selectinload(Product.category),
)


# ---------------------------------------------------------------------------
# Slugs
# ---------------------------------------------------------------------------
class Sluggable(Protocol):
    """Any model with an `id` and a unique `slug`.

    A protocol rather than a union of the three concrete classes: this
    function grew a third caller (emergency aid cases) and would grow a
    fourth, and widening a union at every call site is how a helper ends up
    copied instead of reused.
    """

    id: Any
    slug: Any


async def unique_slug(
    session: AsyncSession,
    model: type[Sluggable],
    source: str,
    *,
    exclude_id: int | None = None,
) -> str:
    """A slug nobody else holds.

    Collisions are resolved with a numeric suffix rather than by rejecting the
    save: two products legitimately called "Kətan köynək" is normal, and
    making the admin invent a unique title to satisfy a URL is backwards.
    """
    base = slugify(source)
    candidate = base
    for attempt in range(2, 200):
        stmt = select(model.id).where(model.slug == candidate)
        if exclude_id is not None:
            stmt = stmt.where(model.id != exclude_id)
        if (await session.execute(stmt)).first() is None:
            return candidate
        candidate = f"{base}-{attempt}"
    # 200 products with the same title is not a naming collision any more.
    raise AppError(ErrorCode.VALIDATION_ERROR, status_code=422, field="slug")


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
async def load_category(session: AsyncSession, category_id: int) -> Category:
    category = (
        await session.execute(
            select(Category)
            .where(Category.id == category_id)
            .options(selectinload(Category.children))
        )
    ).scalar_one_or_none()
    if category is None:
        raise NotFoundError()
    return category


async def _validate_parent(
    session: AsyncSession, parent_id: int | None, *, child_id: int | None = None
) -> None:
    """Depth is capped at two levels (plan.md D11)."""
    if parent_id is None:
        return
    if parent_id == child_id:
        raise AppError(ErrorCode.VALIDATION_ERROR, status_code=422, field="parent_id")

    parent = (
        await session.execute(select(Category).where(Category.id == parent_id))
    ).scalar_one_or_none()
    if parent is None:
        raise AppError(ErrorCode.VALIDATION_ERROR, status_code=422, field="parent_id")
    if parent.parent_id is not None:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            status_code=422,
            field="parent_id",
            details={"reason": "max_depth_2"},
        )
    if child_id is not None:
        # Moving a parent under another category would take its own children
        # to depth three, so a category with children cannot be reparented.
        has_children = (
            await session.execute(select(Category.id).where(Category.parent_id == child_id))
        ).first()
        if has_children is not None:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                status_code=422,
                field="parent_id",
                details={"reason": "has_children"},
            )


async def create_category(session: AsyncSession, data: dict[str, Any]) -> Category:
    await _validate_parent(session, data.get("parent_id"))
    category = Category(
        slug=data.get("slug") or await unique_slug(session, Category, data["name_az"]),
        name_az=data["name_az"],
        name_en=data.get("name_en") or None,
        parent_id=data.get("parent_id"),
        icon=data.get("icon") or None,
        sort_order=data.get("sort_order") or 0,
        is_active=data.get("is_active", True),
    )
    session.add(category)
    await session.flush()
    return category


async def update_category(
    session: AsyncSession, category: Category, data: dict[str, Any]
) -> Category:
    if "parent_id" in data:
        await _validate_parent(session, data["parent_id"], child_id=category.id)
        category.parent_id = data["parent_id"]

    for field in ("name_az", "sort_order", "is_active"):
        if data.get(field) is not None:
            setattr(category, field, data[field])
    if "name_en" in data:
        category.name_en = data["name_en"] or None
    if "icon" in data:
        category.icon = data["icon"] or None
    if data.get("slug"):
        category.slug = await unique_slug(session, Category, data["slug"], exclude_id=category.id)

    await session.flush()
    return category


async def delete_category(session: AsyncSession, category: Category) -> None:
    """Blocked while anything still points at it (plan.md 9.5).

    Cascading would silently take products off the site; reparenting would
    guess at intent. Both are worse than telling the admin what is in the way.
    """
    children = (
        await session.execute(
            select(func.count()).select_from(Category).where(Category.parent_id == category.id)
        )
    ).scalar_one()
    products = (
        await session.execute(
            select(func.count())
            .select_from(Product)
            .where(Product.category_id == category.id, Product.deleted_at.is_(None))
        )
    ).scalar_one()

    if children or products:
        raise AppError(
            ErrorCode.CATEGORY_NOT_EMPTY,
            status_code=409,
            details={"children": children, "products": products},
        )

    await session.delete(category)
    await session.flush()


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
async def load_product(session: AsyncSession, product_id: int) -> Product:
    """Admin lookup: includes soft-deleted rows, so a deletion is reversible."""
    product = (
        await session.execute(
            select(Product).where(Product.id == product_id).options(*PRODUCT_RELATIONS)
        )
    ).scalar_one_or_none()
    if product is None:
        raise NotFoundError()
    return product


async def _require_category(session: AsyncSession, category_id: int) -> Category:
    category = (
        await session.execute(select(Category).where(Category.id == category_id))
    ).scalar_one_or_none()
    if category is None:
        raise AppError(ErrorCode.VALIDATION_ERROR, status_code=422, field="category_id")
    return category


async def create_product(
    session: AsyncSession,
    data: dict[str, Any],
    owner_id: int,
    *,
    status: str = "pending",
    owner: User | None = None,
) -> Product:
    """Create a listing.

    `status` is required at the call site rather than defaulted to approved:
    the whole point of moderation is that publishing is a decision somebody
    makes, and a default of "approved" would make forgetting to pass it
    publish the item.

    `owner` is optional and is used only to inherit a default location
    (FreeShop_Prompt 1). It is a separate argument from `owner_id` because
    the admin create route sets an owner it has not loaded, and loading a row
    just to copy a city from it would be a query for nothing.
    """
    await _require_category(session, data["category_id"])
    product = Product(
        slug=data.get("slug") or await unique_slug(session, Product, data["title_az"]),
        title_az=data["title_az"],
        title_en=data.get("title_en") or None,
        description_az=data.get("description_az") or "",
        description_en=data.get("description_en") or None,
        price_minor=data["price_minor"],
        old_price_minor=data.get("old_price_minor"),
        currency=data.get("currency") or "AZN",
        category_id=data["category_id"],
        stock_status=data.get("stock_status") or "available",
        is_featured=data.get("is_featured", False),
        owner_id=owner_id,
        status=status,
        reviewed_at=datetime.now(UTC) if status != "pending" else None,
        transfer_type=data.get("transfer_type") or "giveaway",
        available_from=data.get("available_from"),
        available_until=data.get("available_until"),
        max_borrow_days=data.get("max_borrow_days"),
    )

    # An explicitly chosen place wins; otherwise the listing inherits the
    # giver's saved default, which is right almost every time and costs them
    # nothing (FreeShop_Prompt 1).
    if data.get("city"):
        geo.apply_to(product, data)
    elif owner is not None:
        geo.copy_from(product, owner)

    product.refresh_search_text()
    session.add(product)
    await session.flush()
    await session.refresh(product, ["images", "category"])
    return product


async def update_product(session: AsyncSession, product: Product, data: dict[str, Any]) -> Product:
    if data.get("category_id") is not None:
        await _require_category(session, data["category_id"])
        product.category_id = data["category_id"]

    for field in (
        "title_az",
        "price_minor",
        "currency",
        "stock_status",
        "is_featured",
        "transfer_type",
    ):
        if data.get(field) is not None:
            setattr(product, field, data[field])

    for field in ("available_from", "available_until", "max_borrow_days"):
        if field in data:
            setattr(product, field, data[field])

    if data.get("city"):
        geo.apply_to(product, data)

    # Nullable fields are cleared by sending "" or null, so an EN translation
    # or a discount ribbon can be removed as well as set (plan.md 7.3).
    if "title_en" in data:
        product.title_en = data["title_en"] or None
    if "description_az" in data:
        product.description_az = data["description_az"] or ""
    if "description_en" in data:
        product.description_en = data["description_en"] or None
    if "old_price_minor" in data:
        product.old_price_minor = data["old_price_minor"]
    if data.get("slug"):
        product.slug = await unique_slug(session, Product, data["slug"], exclude_id=product.id)

    # The folded search copy is derived state; recompute it on every write
    # rather than hoping each call site remembers.
    product.refresh_search_text()
    await session.flush()
    await session.refresh(product, ["images", "category"])
    return product


async def soft_delete_product(session: AsyncSession, product: Product) -> None:
    """Soft delete (plan.md 9.6): gone from the shop, intact in history."""
    if product.deleted_at is None:
        product.deleted_at = datetime.now(UTC)
    await session.flush()


async def restore_product(session: AsyncSession, product: Product) -> None:
    product.deleted_at = None
    await session.flush()


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------
async def attach_image(
    session: AsyncSession, product: Product, path: str, width: int, height: int
) -> ProductImage:
    image = ProductImage(
        product_id=product.id,
        path=path,
        width=width,
        height=height,
        sort_order=len(product.images),
        # The first image of a product is its main image without anyone
        # having to choose one, which is the common case.
        is_main=not product.images,
    )
    session.add(image)
    await session.flush()
    await session.refresh(product, ["images"])
    return image


async def _load_image(session: AsyncSession, product: Product, image_id: int) -> ProductImage:
    image = (
        await session.execute(
            select(ProductImage).where(
                ProductImage.id == image_id, ProductImage.product_id == product.id
            )
        )
    ).scalar_one_or_none()
    if image is None:
        raise NotFoundError()
    return image


async def update_image(
    session: AsyncSession,
    product: Product,
    image_id: int,
    *,
    is_main: bool | None = None,
    sort_order: int | None = None,
) -> ProductImage:
    image = await _load_image(session, product, image_id)

    if sort_order is not None:
        image.sort_order = sort_order
    if is_main:
        # Exactly one main image, enforced here rather than left to a partial
        # unique index that would surface as an opaque IntegrityError.
        for other in product.images:
            other.is_main = other.id == image.id
        image.is_main = True

    await session.flush()
    await session.refresh(product, ["images"])
    return image


async def delete_image(session: AsyncSession, product: Product, image_id: int) -> None:
    image = await _load_image(session, product, image_id)
    was_main = image.is_main
    await session.delete(image)
    await session.flush()
    await session.refresh(product, ["images"])

    # Deleting the main image must not leave the product without one - the
    # card would render a blank tile.
    if was_main and product.images:
        product.images[0].is_main = True
        await session.flush()

    # The file itself is deliberately left on disk: paths are content-hashed,
    # so the same bytes may be referenced by another product, and an orphaned
    # blob is cheaper than a shared image vanishing from someone else's row.


# ---------------------------------------------------------------------------
# Moderation
# ---------------------------------------------------------------------------
async def moderate_product(
    session: AsyncSession, product: Product, *, status: str, note: str | None = None
) -> Product:
    """Approve or reject a submitted listing (plan.md D25).

    An edit after approval does NOT send the item back to the queue: the site
    is for neighbours giving things away, and making someone re-queue for
    fixing a typo is how a moderated board stops being used.
    """
    if status not in ("approved", "rejected"):
        raise AppError(ErrorCode.VALIDATION_ERROR, status_code=422, field="status")

    product.status = status
    product.moderation_note = (note or "").strip() or None
    product.reviewed_at = datetime.now(UTC)

    # A rejected listing must leave the site immediately, even if it was
    # approved a moment ago.
    await session.flush()
    await session.refresh(product, ["images", "category"])
    return product


async def load_own_products(session: AsyncSession, owner_id: int) -> list[Product]:
    """Everything this person has offered, in any state.

    Includes rejected and soft-deleted rows on purpose: "where did my listing
    go?" is the first question someone asks, and an answer of silence is the
    worst one.
    """
    rows = await session.execute(
        select(Product)
        .where(Product.owner_id == owner_id)
        .options(*PRODUCT_RELATIONS)
        .order_by(Product.created_at.desc())
    )
    return list(rows.scalars())


# ---------------------------------------------------------------------------
# Demand on a listing (FreeShop_Prompt 5)
# ---------------------------------------------------------------------------
async def open_request_counts(session: AsyncSession, product_ids: list[int]) -> dict[int, int]:
    """How many people are still waiting on each listing, in one query.

    The public API shows this number and never the names behind it (Rule F).
    Returned as a dict so a page of cards costs one query rather than one per
    card.
    """
    if not product_ids:
        return {}
    rows = await session.execute(
        select(OrderRequestItem.product_id, func.count(OrderRequestItem.id))
        .where(
            OrderRequestItem.product_id.in_(product_ids),
            OrderRequestItem.outcome == "pending",
        )
        .group_by(OrderRequestItem.product_id)
    )
    return {product_id: count for product_id, count in rows.all() if product_id is not None}
