"""The needs board (FreeShop_Prompt 4, 5, 6)."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, Lang, OptionalUser
from app.core.errors import NotFoundError, error_responses
from app.db.models import NeedRequest, OrderRequest, OrderRequestItem
from app.schemas.catalogue import Lang as LangLiteral
from app.schemas.catalogue import Page, ProductCardOut
from app.schemas.needs import (
    ConvertibleItemOut,
    DemandOut,
    MyNeedOut,
    NeedCardOut,
    NeedIn,
    NeedStatusIn,
    NeedUpdateIn,
)
from app.services import geo, matching, need_service, order_service

router = APIRouter(
    prefix="/needs", tags=["needs"], responses=error_responses(401, 403, 404, 409, 422)
)

MAX_PER_PAGE = 60


@router.get("", summary="Browse needs, optionally near you")
async def list_needs(
    session: DbSession,
    lang: Lang,
    response: Response,
    viewer: OptionalUser,
    q: Annotated[str | None, Query(max_length=120)] = None,
    category_id: int | None = None,
    city: Annotated[str | None, Query(max_length=80)] = None,
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
    radius_km: Annotated[float | None, Query(gt=0, le=geo.MAX_RADIUS_KM)] = None,
    sort: Annotated[str, Query(description="newest|nearby")] = "newest",
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=MAX_PER_PAGE)] = 24,
) -> Page[NeedCardOut]:
    """Approved, still-open needs. Names are never included (Rule F)."""
    from app.core.text import normalise_search

    # Needs go stale; this is the only sweep the deployment has (need_service).
    if await need_service.expire_stale(session):
        await session.commit()

    stmt = select(NeedRequest).where(NeedRequest.public())
    if category_id is not None:
        stmt = stmt.where(NeedRequest.category_id == category_id)
    if city:
        stmt = stmt.where(geo.city_matches(NeedRequest, city))
    if q:
        stmt = stmt.where(NeedRequest.search_text.like(f"%{normalise_search(q)}%"))

    origin = geo.origin_or_none(lat, lng, viewer)
    response.headers["Cache-Control"] = "no-store" if viewer else "public, max-age=60"

    if sort == "nearby" and origin is not None:
        o_lat, o_lng = origin
        bounded = stmt
        if radius_km is not None:
            bounded = bounded.where(geo.within_bbox(NeedRequest, o_lat, o_lng, radius_km))
        else:
            bounded = bounded.where(geo.has_coordinates(NeedRequest))

        rows = list(
            (
                await session.execute(
                    bounded.options(selectinload(NeedRequest.category)).limit(geo.CANDIDATE_CAP)
                )
            ).scalars()
        )
        ranked = geo.rank_by_distance(rows, o_lat, o_lng, radius_km=radius_km)
        total = len(ranked)
        window = ranked[(page - 1) * per_page : page * per_page]
        return Page(
            items=[
                NeedCardOut.of(need, lang, distance_km=geo.round_distance(km))
                for need, km in window
            ],
            total=total,
            page=page,
            per_page=per_page,
            pages=(total + per_page - 1) // per_page,
            applied_sort="nearby",
        )

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = list(
        (
            await session.execute(
                stmt.options(selectinload(NeedRequest.category))
                .order_by(NeedRequest.created_at.desc(), NeedRequest.id.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
            )
        ).scalars()
    )

    distances: dict[int, float] = {}
    if origin is not None:
        distances = {
            need.id: geo.round_distance(
                geo.haversine_km(origin[0], origin[1], need.latitude, need.longitude)
            )
            for need in rows
            if need.latitude is not None and need.longitude is not None
        }

    return Page(
        items=[NeedCardOut.of(need, lang, distance_km=distances.get(need.id)) for need in rows],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
        # `nearby` was asked for and could not be honoured - the page still
        # renders, and the client can invite the visitor to add a location.
        applied_sort="newest" if sort == "nearby" else sort,
    )


@router.get("/demand", summary="Aggregated local demand - counts only")
async def demand(
    session: DbSession,
    viewer: OptionalUser,
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
    radius_km: Annotated[float, Query(gt=0, le=geo.MAX_RADIUS_KM)] = 50.0,
    limit: Annotated[int, Query(ge=1, le=30)] = 12,
) -> list[DemandOut]:
    """ "Nərdivan - yaxınlıqda 9 nəfərə lazımdır" (Rule C, Rule F).

    Counts, never identities. Someone who wants to help opens a conversation
    from an individual need, which is an authorised one-to-one act.
    """
    origin = geo.origin_or_none(lat, lng, viewer)
    rows = await matching.demand_nearby(
        session,
        lat=origin[0] if origin else None,
        lng=origin[1] if origin else None,
        radius_km=radius_km if origin else None,
        limit=limit,
    )
    # `demand_nearby` returns plain dicts keyed exactly like DemandOut; the
    # cast is the boundary between that loose shape and the typed DTO.
    return [DemandOut.model_validate(row) for row in rows]


# ---------------------------------------------------------------------------
# Your own needs
# ---------------------------------------------------------------------------
@router.get("/mine", summary="Needs you have posted, in any state")
async def my_needs(user: CurrentUser, session: DbSession, lang: Lang) -> list[MyNeedOut]:
    """Declared before `/{need_id}` so the path is not swallowed by it."""
    rows = await session.execute(
        select(NeedRequest)
        .where(NeedRequest.user_id == user.id)
        .options(selectinload(NeedRequest.category))
        .order_by(NeedRequest.created_at.desc())
    )
    return [MyNeedOut.of_own(need, lang) for need in rows.scalars()]


@router.get("/convertible", summary="Requests that went to someone else")
async def convertible(user: CurrentUser, session: DbSession) -> list[ConvertibleItemOut]:
    """The "Bu əşyanı ala bilmədiniz" prompt (FreeShop_Prompt 5).

    Only lines that lost AND have not already been turned into a need, so the
    offer stops appearing once it has been answered either way.
    """
    items = await order_service.convertible_items(session, user.id)
    return [
        ConvertibleItemOut(
            request_item_id=item.id,
            title=item.title_snapshot,
            product_id=item.product_id,
            quantity=item.quantity,
            decided_at=item.decided_at,
        )
        for item in items
    ]


@router.post(
    "", status_code=status.HTTP_201_CREATED, summary="Post a need - goes to the moderation queue"
)
async def create_need(
    payload: NeedIn, user: CurrentUser, session: DbSession, lang: Lang
) -> MyNeedOut:
    """Anyone signed in may say what they are looking for.

    NO phone gate here, unlike offering an item. Publishing a listing is a
    promise to meet a stranger and hand something over; asking for a
    pushchair is not, and requiring a verified number to admit you need one
    would exclude exactly the people this board is for.
    """
    need = await need_service.create(session, payload.model_dump(), user=user)
    await session.commit()
    return MyNeedOut.of_own(need, lang)


@router.post(
    "/from-request-item/{item_id}",
    status_code=status.HTTP_201_CREATED,
    summary="Keep an unsuccessful request as a need",
)
async def need_from_request(
    item_id: int, user: CurrentUser, session: DbSession, lang: Lang, response: Response
) -> MyNeedOut:
    """ "Ehtiyac kimi saxla" - the consent step (Rule C).

    Returns 200 rather than 201 when the person already had an open need for
    the same thing: nothing new was created, and saying so lets the client
    show "you are already on the list" instead of a second confirmation.
    """
    item = (
        await session.execute(
            select(OrderRequestItem)
            .join(OrderRequest, OrderRequest.id == OrderRequestItem.order_request_id)
            .where(OrderRequestItem.id == item_id, OrderRequest.user_id == user.id)
            .options(selectinload(OrderRequestItem.product))
        )
    ).scalar_one_or_none()
    # Scoped by the owning user, never by id alone (plan.md 10, IDOR).
    if item is None:
        raise NotFoundError()

    need, created = await need_service.from_order_item(session, item, user=user)
    await session.commit()
    if not created:
        response.status_code = status.HTTP_200_OK
    return MyNeedOut.of_own(need, lang)


@router.get("/{need_id}", summary="One need")
async def get_need(
    need_id: int, session: DbSession, lang: Lang, viewer: OptionalUser
) -> NeedCardOut:
    """Public if approved and open; the poster can always see their own.

    Anything else is a 404, including a pending or rejected need - confirming
    that a hidden need exists says something about somebody's circumstances
    that they have not published.
    """
    need = (
        await session.execute(
            select(NeedRequest)
            .where(NeedRequest.id == need_id)
            .options(selectinload(NeedRequest.category))
        )
    ).scalar_one_or_none()
    if need is None:
        raise NotFoundError()
    if not need.is_publicly_visible and (viewer is None or viewer.id != need.user_id):
        raise NotFoundError()

    distance = None
    origin = geo.origin_or_none(None, None, viewer)
    if origin is not None and need.latitude is not None and need.longitude is not None:
        distance = geo.round_distance(
            geo.haversine_km(origin[0], origin[1], need.latitude, need.longitude)
        )
    return NeedCardOut.of(need, lang, distance_km=distance)


@router.get("/{need_id}/matching-listings", summary="Listings that could answer this need")
async def matching_listings(
    need_id: int,
    session: DbSession,
    lang: Lang,
    limit: Annotated[int, Query(ge=1, le=25)] = 8,
    radius_km: Annotated[float | None, Query(gt=0, le=geo.MAX_RADIUS_KM)] = None,
) -> list[ProductCardOut]:
    """The other direction of FreeShop_Prompt 6.

    Public, unlike listing -> needs: these are things people have chosen to
    advertise, so surfacing them to anyone is what they are for.
    """
    need = await need_service.load_public(session, need_id)
    matches = await matching.products_for_need(
        session,
        need,
        limit=limit,
        radius_km=radius_km if radius_km is not None else matching.DEFAULT_RADIUS_KM,
    )
    return [
        ProductCardOut.of(
            product,
            cast("LangLiteral", lang),
            distance_km=geo.round_distance(distance) if distance is not None else None,
        )
        for product, distance, _score in matches
    ]


@router.patch("/{need_id}", summary="Edit your own need")
async def update_need(
    need_id: int, payload: NeedUpdateIn, user: CurrentUser, session: DbSession, lang: Lang
) -> MyNeedOut:
    need = await need_service.load(session, need_id)
    if need.user_id != user.id:
        raise NotFoundError()
    updated = await need_service.update(session, need, payload.model_dump(exclude_unset=True))
    await session.commit()
    return MyNeedOut.of_own(updated, lang)


@router.post("/{need_id}/status", summary="Close, fulfil or reopen your own need")
async def set_need_status(
    need_id: int, payload: NeedStatusIn, user: CurrentUser, session: DbSession, lang: Lang
) -> MyNeedOut:
    need = await need_service.load(session, need_id)
    if need.user_id != user.id:
        raise NotFoundError()
    updated = await need_service.set_status(session, need, payload.status)
    await session.commit()
    return MyNeedOut.of_own(updated, lang)
