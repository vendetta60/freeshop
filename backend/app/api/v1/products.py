"""Public product catalogue (plan.md 6.2, FreeShop_Prompt 1, 2, 5, 6, 7)."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, File, Query, Response, UploadFile, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.selectable import ScalarSelect

from app.api.deps import CurrentUser, DbSession, Lang, OptionalUser, VerifiedUser
from app.config import get_settings
from app.core.errors import AppError, ErrorCode, NotFoundError, error_responses
from app.core.text import normalise_search
from app.db.models import Category, OrderRequestItem, Product
from app.schemas.admin import HandoverIn, MyListingOut, RequesterOut, SubmissionIn
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
from app.schemas.needs import NeedCardOut, NeedMatchOut
from app.services import (
    catalogue_service,
    geo,
    image_service,
    loan_service,
    matching,
    order_service,
)

router = APIRouter(
    prefix="/products", tags=["products"], responses=error_responses(401, 403, 404, 409, 422)
)

MAX_PER_PAGE = 60

# How many rows the nearby sort pulls before ranking them in Python. Bounded
# so a radius of "All" over a large board cannot load the whole table
# (services/geo.py explains why the ranking is not in SQL).
NEARBY_CANDIDATES = geo.CANDIDATE_CAP


def _with_relations(stmt: Select[tuple[Product]]) -> Select[tuple[Product]]:
    """Eager-load everything the serializer touches.

    Without this, rendering a page of 24 cards issues 24 category queries and
    24 image queries. An N+1 in a list endpoint is a build blocker (plan.md 11).
    """
    return stmt.options(selectinload(Product.images), selectinload(Product.category))


def _open_request_count() -> ScalarSelect[int]:
    """Correlated count of people still waiting on a decision.

    A scalar subquery rather than a join and a GROUP BY: the ordering needs
    one number per product and a join would multiply the rows it is trying
    to sort.
    """
    return (
        select(func.count(OrderRequestItem.id))
        .where(
            OrderRequestItem.product_id == Product.id,
            OrderRequestItem.outcome == "pending",
        )
        .correlate(Product)
        .scalar_subquery()
    )


def _apply_sort(
    stmt: Select[tuple[Product]], sort: SortKey, has_query: bool
) -> Select[tuple[Product]]:
    # 'relevance' is only meaningful with a search term; it degrades silently
    # to 'newest' otherwise (plan.md 9.10). 'nearby' is handled by the caller,
    # because it cannot be expressed as an ORDER BY here.
    if sort == "relevance" and not has_query:
        sort = "newest"
    match sort:
        case "price_asc":
            return stmt.order_by(Product.price_minor.asc(), Product.id.desc())
        case "price_desc":
            return stmt.order_by(Product.price_minor.desc(), Product.id.desc())
        case "oldest":
            return stmt.order_by(Product.created_at.asc(), Product.id.asc())
        case "most_requested":
            # Demand is the ranking (Rule C): the things neighbours are
            # actually asking for come first, newest breaking the tie.
            return stmt.order_by(_open_request_count().desc(), Product.created_at.desc())
        case _:
            return stmt.order_by(Product.created_at.desc(), Product.id.desc())


async def _decorate(
    session: DbSession,
    products: list[Product],
    lang: str,
    distances: dict[int, float] | None = None,
) -> list[ProductCardOut]:
    """Cards with their loan state resolved in ONE extra query for the page."""
    loan_ids = [p.id for p in products if p.is_loan]
    states = await loan_service.listing_states(session, loan_ids)
    return [
        ProductCardOut.of(
            product,
            cast("LangLiteral", lang),
            distance_km=(distances or {}).get(product.id),
            loan_state=states.get(product.id, "available"),
        )
        for product in products
    ]


@router.get("", summary="List products with filter, search, sort and pagination")
async def list_products(
    session: DbSession,
    lang: Lang,
    response: Response,
    viewer: OptionalUser,
    q: Annotated[str | None, Query(max_length=120)] = None,
    category: Annotated[str | None, Query(description="Category slug")] = None,
    category_id: int | None = None,
    min_price: Annotated[int | None, Query(ge=0, description="Minor units")] = None,
    max_price: Annotated[int | None, Query(ge=0)] = None,
    stock: Annotated[str | None, Query(description="available|out_of_stock|on_order")] = None,
    featured: bool | None = None,
    transfer_type: Annotated[str | None, Query(description="giveaway|loan")] = None,
    city: Annotated[str | None, Query(max_length=80)] = None,
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
    radius_km: Annotated[float | None, Query(gt=0, le=geo.MAX_RADIUS_KM)] = None,
    sort: SortKey = "newest",
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=MAX_PER_PAGE)] = 24,
) -> Page[ProductCardOut]:
    """The catalogue.

    NEARBY (FreeShop_Prompt 2): `sort=nearby` measures from `lat`/`lng` when
    they are given and from the signed-in visitor's saved location otherwise.
    When there is neither, the request does NOT fail - it falls back to
    newest-first and says so in `applied_sort`, which is what lets the client
    explain that adding a location would improve the results.
    """
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
    if transfer_type in ("giveaway", "loan"):
        stmt = stmt.where(Product.transfer_type == transfer_type)
    if city:
        # A named place, for a visitor who wants a town rather than a radius.
        # Works for rows the gazetteer could not place, which a distance
        # filter cannot (services/geo.py).
        stmt = stmt.where(geo.city_matches(Product, city))

    if q:
        # Matched against the folded copy, so "ketan" finds "Kətan".
        # FTS5 replaces this behind the same signature once ranking is needed
        # (plan.md D8); the folded column stays useful either way.
        stmt = stmt.where(Product.search_text.like(f"%{normalise_search(q)}%"))

    origin = geo.origin_or_none(lat, lng, viewer)
    applied: SortKey = sort

    # --- the nearby branch --------------------------------------------------
    if sort == "nearby" and origin is None:
        applied = "newest"
    elif sort == "nearby" or (radius_km is not None and origin is not None):
        assert origin is not None
        o_lat, o_lng = origin
        bounded = stmt
        if radius_km is not None:
            bounded = bounded.where(geo.within_bbox(Product, o_lat, o_lng, radius_km))
        else:
            bounded = bounded.where(geo.has_coordinates(Product))

        rows = list(
            (await session.execute(_with_relations(bounded).limit(NEARBY_CANDIDATES))).scalars()
        )
        ranked = geo.rank_by_distance(rows, o_lat, o_lng, radius_km=radius_km)

        total = len(ranked)
        window = ranked[(page - 1) * per_page : page * per_page]
        distances: dict[int, float] = {product.id: geo.round_distance(km) for product, km in window}
        items = await _decorate(session, [p for p, _ in window], lang, distances)

        response.headers["Cache-Control"] = "no-store"
        return Page(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            pages=(total + per_page - 1) // per_page,
            applied_sort="nearby" if sort == "nearby" else sort,
        )

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

    stmt = _apply_sort(stmt, applied, bool(q))
    stmt = _with_relations(stmt).offset((page - 1) * per_page).limit(per_page)
    products = list((await session.execute(stmt)).scalars())

    # A distance is still useful when the ORDER BY was something else, so it
    # is computed for whatever this page happens to contain.
    page_distances: dict[int, float] = {}
    if origin is not None:
        page_distances = {
            product.id: geo.round_distance(
                geo.haversine_km(origin[0], origin[1], product.latitude, product.longitude)
            )
            for product in products
            if product.latitude is not None and product.longitude is not None
        }

    # Personalised by the viewer's saved location, so it must not be cached
    # in a shared proxy.
    response.headers["Cache-Control"] = (
        "no-store" if viewer is not None else "public, max-age=60, stale-while-revalidate=300"
    )
    return Page(
        items=await _decorate(session, products, lang, page_distances),
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
        applied_sort=applied,
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
    counts = await catalogue_service.open_request_counts(session, [p.id for p in products])
    return [
        MyListingOut.of(p, cast("LangLiteral", lang), open_request_count=counts.get(p.id, 0))
        for p in products
    ]


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

    Three deliberate properties:

    * The listing is created `pending`. Nothing a stranger writes appears on
      the site until a person has read it.
    * The phone gate stays (plan.md 9.3). A giveaway is a promise to meet
      somebody, and the number behind it has to have been proven once.
    * The location defaults to the giver's saved one (FreeShop_Prompt 1), so
      the common case costs no extra typing.
    """
    product = await catalogue_service.create_product(
        session, payload.model_dump(), owner_id=user.id, status="pending", owner=user
    )
    await session.commit()
    return MyListingOut.of(product, cast("LangLiteral", lang))


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


# ---------------------------------------------------------------------------
# Choosing who receives it (FreeShop_Prompt 5, Rule C)
# ---------------------------------------------------------------------------
@router.get("/{product_id}/requesters", summary="Who has asked for your listing")
async def list_requesters(
    product_id: int, user: CurrentUser, session: DbSession
) -> list[RequesterOut]:
    """The giver's view, and only the giver's.

    The public API returns a COUNT of people waiting (Rule F). This returns
    the names, because choosing between them is the decision the owner has to
    make - and it is a 404 for anybody else, so an id cannot be probed.
    """
    product = await catalogue_service.load_product(session, product_id)
    if product.owner_id != user.id:
        raise NotFoundError()

    items = await order_service.requesters_for(session, product_id)
    return [
        RequesterOut(
            request_item_id=item.id,
            request_no=item.order_request.request_no,
            user_id=item.order_request.user_id,
            display_name=item.order_request.user.display_name,
            note=item.order_request.note,
            quantity=item.quantity,
            requested_at=item.created_at,
        )
        for item in items
    ]


@router.post("/{product_id}/handover", summary="Mark the listing given to one requester")
async def hand_over(
    product_id: int, payload: HandoverIn, user: CurrentUser, session: DbSession
) -> list[RequesterOut]:
    """One person receives it; the rest become recorded, consenting demand.

    Returns the people who were NOT selected, so the owner sees what happened
    rather than watching a list empty itself. Nobody's request is deleted -
    see services/order_service.hand_over for why that is the whole point.
    """
    product = await catalogue_service.load_product(session, product_id)
    if product.owner_id != user.id:
        raise NotFoundError()

    _, others = await order_service.hand_over(
        session, product=product, chosen_item_id=payload.request_item_id, owner=user
    )
    await session.commit()

    return [
        RequesterOut(
            request_item_id=item.id,
            request_no=item.order_request.request_no,
            user_id=item.order_request.user_id,
            display_name=item.order_request.user.display_name,
            note=None,
            quantity=item.quantity,
            requested_at=item.created_at,
        )
        for item in others
    ]


@router.get("/{product_id}/matching-needs", summary="Open needs this listing could answer")
async def matching_needs(
    product_id: int,
    session: DbSession,
    lang: Lang,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=25)] = 8,
    radius_km: Annotated[float | None, Query(gt=0, le=geo.MAX_RADIUS_KM)] = None,
) -> list[NeedMatchOut]:
    """ "Yaxınlıqda 4 nəfər bu tip əşya axtarır" (FreeShop_Prompt 6).

    Signed-in only. The needs themselves are public, but a list of who wants
    what, keyed to a listing, is exactly the aggregation Rule F asks us not
    to hand to anonymous callers.
    """
    product = await catalogue_service.load_product(session, product_id)
    matches = await matching.needs_for_product(
        session,
        product,
        limit=limit,
        radius_km=radius_km if radius_km is not None else matching.DEFAULT_RADIUS_KM,
    )
    return [
        NeedMatchOut(
            need=NeedCardOut.of(
                need,
                lang,
                distance_km=geo.round_distance(distance) if distance is not None else None,
            ),
            score=round(value, 3),
        )
        for need, distance, value in matches
    ]


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------
@router.get("/{slug}", summary="Product detail by slug or id")
async def get_product(
    slug: str, session: DbSession, lang: Lang, viewer: OptionalUser
) -> ProductDetailOut:
    stmt = select(Product).where(Product.public())
    # Accept an id too, so an admin can paste a raw id and get the page.
    stmt = (
        stmt.where(Product.id == int(slug)) if slug.isdigit() else stmt.where(Product.slug == slug)
    )

    product = (await session.execute(_with_relations(stmt))).scalar_one_or_none()
    if product is None:
        raise NotFoundError()

    origin = geo.origin_or_none(None, None, viewer)
    distance = None
    if origin is not None and product.latitude is not None and product.longitude is not None:
        distance = geo.round_distance(
            geo.haversine_km(origin[0], origin[1], product.latitude, product.longitude)
        )

    counts = await catalogue_service.open_request_counts(session, [product.id])
    return ProductDetailOut.of(
        product,
        cast("LangLiteral", lang),
        distance_km=distance,
        loan_state=await loan_service.listing_state(session, product),
        open_request_count=counts.get(product.id, 0),
    )


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
    return await _decorate(session, products, lang)
