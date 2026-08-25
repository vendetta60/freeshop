"""Public product catalogue (plan.md 6.2)."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, File, Query, Response, UploadFile, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, Lang, VerifiedUser
from app.config import get_settings
from app.core.errors import AppError, ErrorCode, NotFoundError, error_responses
from app.core.text import normalise_search
from app.db.models import Category, Product
from app.schemas.admin import MyListingOut, SubmissionIn
from app.schemas.catalogue import (
    ImageOut,
    Page,
    ProductCardOut,
    ProductDetailOut,
    SortKey,
)
from app.schemas.catalogue import (
    Lang as LangLiteral,
)
from app.services import catalogue_service, image_service

router = APIRouter(
    prefix="/products", tags=["products"], responses=error_responses(401, 403, 404, 422)
)

MAX_PER_PAGE = 60


def _with_relations(stmt: Select[tuple[Product]]) -> Select[tuple[Product]]:
    """Eager-load everything the serializer touches.

    Without this, rendering a page of 24 cards issues 24 category queries and
    24 image queries. An N+1 in a list endpoint is a build blocker (plan.md 11).
    """
    return stmt.options(selectinload(Product.images), selectinload(Product.category))


def _apply_sort(
    stmt: Select[tuple[Product]], sort: SortKey, has_query: bool
) -> Select[tuple[Product]]:
    # 'relevance' is only meaningful with a search term; it degrades silently
    # to 'newest' otherwise (plan.md 9.10).
    if sort == "relevance" and not has_query:
        sort = "newest"
    match sort:
        case "price_asc":
            return stmt.order_by(Product.price_minor.asc(), Product.id.desc())
        case "price_desc":
            return stmt.order_by(Product.price_minor.desc(), Product.id.desc())
        case "oldest":
            return stmt.order_by(Product.created_at.asc(), Product.id.asc())
        case _:
            return stmt.order_by(Product.created_at.desc(), Product.id.desc())


@router.get("", summary="List products with filter, search, sort and pagination")
async def list_products(
    session: DbSession,
    lang: Lang,
    response: Response,
    q: Annotated[str | None, Query(max_length=120)] = None,
    category: Annotated[str | None, Query(description="Category slug")] = None,
    category_id: int | None = None,
    min_price: Annotated[int | None, Query(ge=0, description="Minor units")] = None,
    max_price: Annotated[int | None, Query(ge=0)] = None,
    stock: Annotated[str | None, Query(description="available|out_of_stock|on_order")] = None,
    featured: bool | None = None,
    sort: SortKey = "newest",
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=MAX_PER_PAGE)] = 24,
) -> Page[ProductCardOut]:
    stmt = select(Product).where(Product.public())

    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    elif category:
        # A parent slug includes everything beneath it, which is what clicking
        # a top-level category is expected to do.
        target = (
            await session.execute(select(Category).where(Category.slug == category))
        ).scalar_one_or_none()
        if target is None:
            return Page(items=[], total=0, page=page, per_page=per_page, pages=0)
        child_ids = [
            row[0]
            for row in (
                await session.execute(select(Category.id).where(Category.parent_id == target.id))
            ).all()
        ]
        stmt = stmt.where(Product.category_id.in_([target.id, *child_ids]))

    if min_price is not None:
        stmt = stmt.where(Product.price_minor >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price_minor <= max_price)
    if stock:
        stmt = stmt.where(Product.stock_status == stock)
    if featured is not None:
        stmt = stmt.where(Product.is_featured.is_(featured))

    if q:
        # Matched against the folded copy, so "ketan" finds "Kətan".
        # FTS5 replaces this behind the same signature once ranking is needed
        # (plan.md D8); the folded column stays useful either way.
        stmt = stmt.where(Product.search_text.like(f"%{normalise_search(q)}%"))

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

    stmt = _apply_sort(stmt, sort, bool(q))
    stmt = _with_relations(stmt).offset((page - 1) * per_page).limit(per_page)
    products = list((await session.execute(stmt)).scalars())

    response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=300"
    return Page(
        items=[ProductCardOut.of(p, cast(LangLiteral, lang)) for p in products],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


# ---------------------------------------------------------------------------
# Offering something (plan.md D25)
# ---------------------------------------------------------------------------
@router.get("/mine", summary="Listings you have offered, in any state")
async def my_listings(user: CurrentUser, session: DbSession, lang: Lang) -> list[MyListingOut]:
    """Declared BEFORE `/{slug}` so the path is not swallowed by it.

    Returns pending, approved, rejected and soft-deleted rows alike: "where
    did my listing go?" needs an answer, and silence is the worst one.
    """
    products = await catalogue_service.load_own_products(session, user.id)
    return [MyListingOut.of(p, cast(LangLiteral, lang)) for p in products]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Offer an item - goes to the moderation queue",
)
async def submit_listing(
    payload: SubmissionIn,
    user: VerifiedUser,
    session: DbSession,
    lang: Lang,
) -> MyListingOut:
    """Anyone signed in with a verified phone may offer something.

    Two deliberate properties:

    * The listing is created `pending`. Nothing a stranger writes appears on
      the site until a person has read it.
    * The phone gate stays (plan.md 9.3). A giveaway is a promise to meet
      somebody, and the number behind it has to have been proven once.
    """
    product = await catalogue_service.create_product(
        session, payload.model_dump(), owner_id=user.id, status="pending"
    )
    await session.commit()
    return MyListingOut.of(product, cast(LangLiteral, lang))


@router.post(
    "/{product_id}/images",
    status_code=status.HTTP_201_CREATED,
    summary="Add photos to a listing you offered",
)
async def upload_listing_images(
    product_id: int,
    user: CurrentUser,
    session: DbSession,
    files: Annotated[list[UploadFile], File(description="Up to 8 images, 5 MB each")],
) -> list[ImageOut]:
    """Photos for your own listing.

    A giveaway without a photograph is an advert nobody answers, so this has
    to be open to the person offering the item and not only to the
    administrator. It is the SAME pipeline as the admin route - sniffed,
    re-encoded, EXIF stripped, content-addressed (plan.md 9.7) - because a
    second, more relaxed upload path is the one that gets exploited.

    Ownership is the whole authorisation check: a listing that is not yours is
    a 404, so the endpoint never confirms that someone else's id exists.
    """
    settings = get_settings()
    product = await catalogue_service.load_product(session, product_id)
    if product.owner_id != user.id:
        raise NotFoundError()

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
    return [ImageOut.of(image) for image in images]


@router.get("/{slug}", summary="Product detail by slug or id")
async def get_product(slug: str, session: DbSession, lang: Lang) -> ProductDetailOut:
    stmt = select(Product).where(Product.public())
    # Accept an id too, so an admin can paste a raw id and get the page.
    stmt = (
        stmt.where(Product.id == int(slug)) if slug.isdigit() else stmt.where(Product.slug == slug)
    )

    product = (await session.execute(_with_relations(stmt))).scalar_one_or_none()
    if product is None:
        raise NotFoundError()
    return ProductDetailOut.of(product, cast(LangLiteral, lang))


@router.get("/{slug}/related", summary="Products in the same category")
async def related_products(
    slug: str,
    session: DbSession,
    lang: Lang,
    limit: Annotated[int, Query(ge=1, le=12)] = 4,
) -> list[ProductCardOut]:
    product = (
        await session.execute(select(Product).where(Product.slug == slug, Product.public()))
    ).scalar_one_or_none()
    if product is None:
        raise NotFoundError()

    stmt = (
        select(Product)
        .where(
            Product.category_id == product.category_id,
            Product.id != product.id,
            Product.public(),
        )
        .order_by(Product.created_at.desc())
        .limit(limit)
    )
    products = list((await session.execute(_with_relations(stmt))).scalars())
    return [ProductCardOut.of(p, cast(LangLiteral, lang)) for p in products]
