"""Admin panel API (plan.md 6.2, 11).

Every route in this module is behind `require_admin`, which re-reads the role
from the database on each request. The frontend's route guard is UX; this is
the control (plan.md 10).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, File, Query, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import AdminUser, DbSession, VerifiedUser
from app.config import get_settings
from app.core.errors import AppError, ErrorCode, error_responses
from app.core.logging import get_logger
from app.core.text import normalise_search
from app.db.models import Category, OrderRequest, Product, User
from app.schemas.admin import (
    AdminCategoryOut,
    AdminProductOut,
    AdminRequestSummary,
    AdminUserOut,
    CategoryIn,
    CategoryUpdateIn,
    DayCount,
    ImageUpdateIn,
    ModerationIn,
    ProductIn,
    ProductUpdateIn,
    SettingsUpdateIn,
    StatsOut,
)
from app.schemas.catalogue import ImageOut, Page
from app.services import catalogue_service, image_service, settings_service

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    responses=error_responses(400, 401, 403, 404, 409, 422),
)
log = get_logger(__name__)

NO_STORE = {"Cache-Control": "no-store"}


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
@router.get("/products", summary="Product table [admin]")
async def list_products(
    admin: AdminUser,
    session: DbSession,
    response: Response,
    q: Annotated[str | None, Query(max_length=120)] = None,
    category_id: int | None = None,
    stock: Annotated[str | None, Query(description="available|out_of_stock|on_order")] = None,
    status_filter: Annotated[
        str | None, Query(alias="status", description="pending|approved|rejected")
    ] = None,
    include_deleted: bool = False,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 25,
) -> Page[AdminProductOut]:
    """The admin listing, unlike the public one, can show deleted rows.

    A soft delete that the panel cannot see is indistinguishable from a hard
    delete, which would make the whole mechanism pointless (plan.md 9.6).
    """
    response.headers.update(NO_STORE)

    stmt = select(Product)
    if not include_deleted:
        stmt = stmt.where(Product.deleted_at.is_(None))
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    if stock:
        stmt = stmt.where(Product.stock_status == stock)
    if status_filter:
        stmt = stmt.where(Product.status == status_filter)
    if q:
        stmt = stmt.where(Product.search_text.like(f"%{normalise_search(q)}%"))

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

    stmt = (
        stmt.options(*catalogue_service.PRODUCT_RELATIONS, selectinload(Product.owner))
        # Oldest first when reviewing: a queue that shows the newest first
        # leaves the person who waited longest at the bottom.
        .order_by(
            Product.created_at.asc() if status_filter == "pending" else Product.created_at.desc(),
            Product.id.desc(),
        )
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    products = list((await session.execute(stmt)).scalars())

    return Page(
        items=[AdminProductOut.of(p, owner_loaded=True) for p in products],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@router.get("/products/{product_id}", summary="One product, raw bilingual fields [admin]")
async def get_product(product_id: int, admin: AdminUser, session: DbSession) -> AdminProductOut:
    return AdminProductOut.of(await catalogue_service.load_product(session, product_id))


@router.post(
    "/products",
    status_code=status.HTTP_201_CREATED,
    summary="Publish a product [admin + verified phone]",
)
async def create_product(
    payload: ProductIn,
    publisher: VerifiedUser,
    admin: AdminUser,
    session: DbSession,
) -> AdminProductOut:
    """Publishing is the one action gated on a verified phone (plan.md 9.3).

    A listing carries a seller's contact details, so the number behind it has
    to have been proven at least once. The gate returns PHONE_NOT_VERIFIED
    rather than a generic 403, which is what lets the panel open the verify
    modal instead of showing a dead end.
    """
    # An administrator publishing directly IS the review, so this skips the
    # queue. Everything submitted through `POST /products` starts pending.
    product = await catalogue_service.create_product(
        session, payload.model_dump(), owner_id=admin.id, status="approved"
    )
    await session.commit()
    log.info("product_created", product_id=product.id, admin_id=admin.id)
    return AdminProductOut.of(product)


@router.patch("/products/{product_id}", summary="Edit a product [admin]")
async def update_product(
    product_id: int,
    payload: ProductUpdateIn,
    admin: AdminUser,
    session: DbSession,
) -> AdminProductOut:
    product = await catalogue_service.load_product(session, product_id)
    # exclude_unset, not exclude_none: an explicit null clears a nullable
    # field, while an absent key leaves it alone. Collapsing the two would
    # make it impossible to remove an EN translation once added.
    product = await catalogue_service.update_product(
        session, product, payload.model_dump(exclude_unset=True)
    )
    await session.commit()
    return AdminProductOut.of(product)


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a product [admin]",
)
async def delete_product(product_id: int, admin: AdminUser, session: DbSession) -> None:
    product = await catalogue_service.load_product(session, product_id)
    await catalogue_service.soft_delete_product(session, product)
    await session.commit()
    log.info("product_deleted", product_id=product_id, admin_id=admin.id)


@router.post("/products/{product_id}/moderate", summary="Approve or reject a listing [admin]")
async def moderate_product(
    product_id: int,
    payload: ModerationIn,
    admin: AdminUser,
    session: DbSession,
) -> AdminProductOut:
    """The decision that puts an offer on the site, or does not.

    A rejection carries a note. Turning someone's donation down without a
    reason is the fastest way to lose the next one.
    """
    product = await catalogue_service.load_product(session, product_id)
    product = await catalogue_service.moderate_product(
        session, product, status=payload.status, note=payload.note
    )
    await session.commit()
    log.info(
        "product_moderated",
        product_id=product_id,
        decision=payload.status,
        admin_id=admin.id,
    )
    return AdminProductOut.of(product)


@router.post("/products/{product_id}/restore", summary="Undo a soft delete [admin]")
async def restore_product(product_id: int, admin: AdminUser, session: DbSession) -> AdminProductOut:
    product = await catalogue_service.load_product(session, product_id)
    await catalogue_service.restore_product(session, product)
    await session.commit()
    return AdminProductOut.of(product)


# ---------------------------------------------------------------------------
# Product images
# ---------------------------------------------------------------------------
@router.post(
    "/products/{product_id}/images",
    status_code=status.HTTP_201_CREATED,
    summary="Upload product images [admin]",
)
async def upload_images(
    product_id: int,
    admin: AdminUser,
    session: DbSession,
    files: Annotated[list[UploadFile], File(description="Up to 8 images, 5 MB each")],
) -> list[ImageOut]:
    """Sniffed, re-encoded and stored under a content-addressed path.

    The upload is validated per file before anything is written, so a batch
    with one bad file fails loudly rather than half-succeeding.
    """
    settings = get_settings()
    product = await catalogue_service.load_product(session, product_id)

    room = settings.max_images_per_product - len(product.images)
    if len(files) > room:
        raise AppError(
            ErrorCode.UPLOAD_REJECTED,
            status_code=400,
            field="files",
            details={"reason": "too_many", "limit": settings.max_images_per_product, "room": room},
        )

    stored = []
    for upload in files:
        # Read one byte past the limit so an oversize file is detected without
        # pulling the whole thing into memory.
        data = await upload.read(settings.max_upload_bytes + 1)
        stored.append(
            image_service.store(
                data, settings.resolved_upload_dir, max_bytes=settings.max_upload_bytes
            )
        )

    images = [
        await catalogue_service.attach_image(session, product, s.path, s.width, s.height)
        for s in stored
    ]
    await session.commit()
    log.info("images_uploaded", product_id=product_id, count=len(images))
    return [ImageOut.of(image) for image in images]


@router.patch(
    "/products/{product_id}/images/{image_id}",
    summary="Reorder or pick the main image [admin]",
)
async def update_image(
    product_id: int,
    image_id: int,
    payload: ImageUpdateIn,
    admin: AdminUser,
    session: DbSession,
) -> AdminProductOut:
    product = await catalogue_service.load_product(session, product_id)
    await catalogue_service.update_image(
        session, product, image_id, is_main=payload.is_main, sort_order=payload.sort_order
    )
    await session.commit()
    return AdminProductOut.of(product)


@router.delete(
    "/products/{product_id}/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an image [admin]",
)
async def delete_image(
    product_id: int, image_id: int, admin: AdminUser, session: DbSession
) -> None:
    product = await catalogue_service.load_product(session, product_id)
    await catalogue_service.delete_image(session, product, image_id)
    await session.commit()


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
async def _category_counts(session: DbSession) -> dict[int, int]:
    rows = (
        await session.execute(
            select(Product.category_id, func.count())
            .where(Product.deleted_at.is_(None))
            .group_by(Product.category_id)
        )
    ).all()
    return {int(cid): int(count) for cid, count in rows}


@router.get("/categories", summary="Flat category list with product counts [admin]")
async def list_categories(
    admin: AdminUser, session: DbSession, response: Response
) -> list[AdminCategoryOut]:
    """Flat, not a tree: the manager renders parents and children in one
    table with an indent, and a nested payload would only be flattened again
    on arrival."""
    response.headers.update(NO_STORE)
    counts = await _category_counts(session)
    categories = list(
        (
            await session.execute(
                select(Category).order_by(
                    Category.parent_id.is_(None).desc(), Category.sort_order, Category.name_az
                )
            )
        ).scalars()
    )
    return [AdminCategoryOut.of(c, counts) for c in categories]


@router.post(
    "/categories", status_code=status.HTTP_201_CREATED, summary="Create a category [admin]"
)
async def create_category(
    payload: CategoryIn, admin: AdminUser, session: DbSession
) -> AdminCategoryOut:
    category = await catalogue_service.create_category(session, payload.model_dump())
    await session.commit()
    return AdminCategoryOut.of(category)


@router.patch("/categories/{category_id}", summary="Edit a category [admin]")
async def update_category(
    category_id: int, payload: CategoryUpdateIn, admin: AdminUser, session: DbSession
) -> AdminCategoryOut:
    category = await catalogue_service.load_category(session, category_id)
    category = await catalogue_service.update_category(
        session, category, payload.model_dump(exclude_unset=True)
    )
    await session.commit()
    return AdminCategoryOut.of(category)


@router.delete(
    "/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an empty category [admin]",
)
async def delete_category(category_id: int, admin: AdminUser, session: DbSession) -> None:
    category = await catalogue_service.load_category(session, category_id)
    await catalogue_service.delete_category(session, category)
    await session.commit()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
@router.get("/users", summary="Registered users [admin]")
async def list_users(
    admin: AdminUser,
    session: DbSession,
    response: Response,
    q: Annotated[str | None, Query(max_length=60)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 25,
) -> Page[AdminUserOut]:
    response.headers.update(NO_STORE)

    stmt = select(User)
    if q:
        needle = f"%{q.strip()}%"
        stmt = stmt.where(
            User.phone.like(needle) | User.email.like(needle) | User.full_name.like(needle)
        )

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    users = list(
        (
            await session.execute(
                stmt.order_by(User.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
            )
        ).scalars()
    )

    counts: dict[int, int] = {
        int(user_id): int(count)
        for user_id, count in (
            await session.execute(
                select(OrderRequest.user_id, func.count()).group_by(OrderRequest.user_id)
            )
        ).all()
    }
    return Page(
        items=[AdminUserOut.of(u, counts.get(u.id, 0)) for u in users],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
@router.get("/settings", summary="Every site setting [admin]")
async def read_settings(admin: AdminUser, session: DbSession, response: Response) -> dict[str, Any]:
    """Defaults merged with overrides, so the form is never blank for a key
    that has simply never been written."""
    response.headers.update(NO_STORE)
    return await settings_service.load_all(session)


@router.patch("/settings", summary="Update site settings [admin]")
async def write_settings(
    payload: SettingsUpdateIn, admin: AdminUser, session: DbSession
) -> dict[str, Any]:
    unknown = payload.unknown()
    if unknown:
        # Refused rather than ignored: a silently dropped key looks saved in
        # the panel and is invisible everywhere else.
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            status_code=422,
            field="values",
            details={"unknown_keys": unknown},
        )

    await settings_service.update(session, payload.known())
    await session.commit()
    log.info("settings_updated", keys=sorted(payload.known()), admin_id=admin.id)
    return await settings_service.load_all(session)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@router.get("/stats", summary="Dashboard counters and a 30-day series [admin]")
async def stats(admin: AdminUser, session: DbSession, response: Response) -> StatsOut:
    response.headers.update(NO_STORE)

    async def count(model: type, *where: Any) -> int:
        stmt = select(func.count()).select_from(model)
        for clause in where:
            stmt = stmt.where(clause)
        return (await session.execute(stmt)).scalar_one()

    since = datetime.now(UTC) - timedelta(days=29)
    recent = list(
        (
            await session.execute(
                select(OrderRequest.created_at).where(OrderRequest.created_at >= since)
            )
        ).scalars()
    )
    # Bucketed in Python rather than with date() in SQL: SQLite stores these
    # as text without a timezone, so the grouping would silently be in
    # whatever the writer's local time was (see UtcDateTime in db/base.py).
    buckets: dict[str, int] = {}
    for created in recent:
        stamp = created if created.tzinfo else created.replace(tzinfo=UTC)
        buckets[stamp.astimezone(UTC).date().isoformat()] = (
            buckets.get(stamp.astimezone(UTC).date().isoformat(), 0) + 1
        )

    today = datetime.now(UTC).date()
    series = [
        DayCount(
            date=(today - timedelta(days=offset)).isoformat(),
            count=buckets.get((today - timedelta(days=offset)).isoformat(), 0),
        )
        for offset in range(29, -1, -1)
    ]

    revenue = (
        await session.execute(
            select(func.coalesce(func.sum(OrderRequest.total_minor), 0)).where(
                OrderRequest.status != "cancelled"
            )
        )
    ).scalar_one()

    return StatsOut(
        products=await count(Product, Product.public()),
        products_pending=await count(
            Product, Product.status == "pending", Product.deleted_at.is_(None)
        ),
        products_deleted=await count(Product, Product.deleted_at.is_not(None)),
        categories=await count(Category),
        users=await count(User),
        requests_total=await count(OrderRequest),
        requests_new=await count(OrderRequest, OrderRequest.status == "new"),
        requests_completed=await count(OrderRequest, OrderRequest.status == "completed"),
        revenue_requested_minor=int(revenue),
        series=series,
    )


@router.get("/stats/recent-requests", summary="Latest requests for the dashboard [admin]")
async def recent_requests(
    admin: AdminUser,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> list[AdminRequestSummary]:
    requests = list(
        (
            await session.execute(
                select(OrderRequest)
                .options(selectinload(OrderRequest.items))
                .order_by(OrderRequest.created_at.desc())
                .limit(limit)
            )
        ).scalars()
    )
    return [AdminRequestSummary.of(r) for r in requests]
