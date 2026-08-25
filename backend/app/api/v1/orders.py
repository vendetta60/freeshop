"""Order requests: submission, history, and admin management (plan.md 6.2)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import AdminUser, CurrentUser, DbSession, Lang
from app.core.errors import NotFoundError, error_responses
from app.db.models import OrderRequest, OrderRequestItem, Product
from app.schemas.cart import (
    AdminOrderRequestOut,
    CreateOrderRequestIn,
    OrderRequestCreatedOut,
    OrderRequestOut,
    UpdateOrderRequestIn,
)
from app.schemas.catalogue import Page
from app.services import order_service

router = APIRouter(tags=["order-requests"], responses=error_responses(401, 403, 404, 422))


@router.post(
    "/order-requests",
    status_code=status.HTTP_201_CREATED,
    summary="Turn the cart into a contact request",
)
async def create_order_request(
    payload: CreateOrderRequestIn,
    user: CurrentUser,
    session: DbSession,
    lang: Lang,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> OrderRequestCreatedOut:
    request, created = await order_service.create_from_cart(
        session,
        user,
        contact_phone=payload.contact_phone,
        contact_email=payload.contact_email,
        note=payload.note,
        idempotency_key=idempotency_key,
    )
    await session.commit()

    if not created:
        # A replay, not a new request. 200 tells the client nothing new
        # happened, which matters if it is retrying.
        response.status_code = status.HTTP_200_OK

    return OrderRequestCreatedOut(
        request=OrderRequestOut.of(request),
        # The seller's channels ship with the confirmation: being told "we got
        # it" without being told how to reach anyone is the failure mode this
        # whole flow exists to avoid (plan.md 9.1).
        contact=await order_service.seller_contact(session, lang),
    )


@router.get("/order-requests/me", summary="Your own requests")
async def my_requests(user: CurrentUser, session: DbSession) -> list[OrderRequestOut]:
    requests = await order_service.load_for_user(session, user.id)
    return [OrderRequestOut.of(r) for r in requests]


@router.get("/order-requests/me/{request_id}", summary="One of your requests")
async def my_request(request_id: int, user: CurrentUser, session: DbSession) -> OrderRequestOut:
    request = (
        await session.execute(
            select(OrderRequest)
            .where(OrderRequest.id == request_id, OrderRequest.user_id == user.id)
            .options(
                selectinload(OrderRequest.items)
                .selectinload(OrderRequestItem.product)
                .selectinload(Product.images)
            )
        )
    ).scalar_one_or_none()
    # Filtered by user_id, never by id alone (plan.md 10, IDOR).
    if request is None:
        raise NotFoundError()
    return OrderRequestOut.of(request)


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
@router.get("/admin/order-requests", summary="All requests [admin]")
async def list_requests(
    admin: AdminUser,
    session: DbSession,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    q: Annotated[str | None, Query(max_length=60)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 25,
) -> Page[AdminOrderRequestOut]:
    stmt = select(OrderRequest)
    if status_filter:
        stmt = stmt.where(OrderRequest.status == status_filter)
    if q:
        stmt = stmt.where(OrderRequest.request_no.like(f"%{q.strip().upper()}%"))

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

    stmt = (
        stmt.options(
            selectinload(OrderRequest.user),
            selectinload(OrderRequest.items)
            .selectinload(OrderRequestItem.product)
            .selectinload(Product.images),
        )
        .order_by(OrderRequest.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    requests = list((await session.execute(stmt)).scalars())

    return Page(
        items=[AdminOrderRequestOut.of_admin(r) for r in requests],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@router.patch("/admin/order-requests/{request_id}", summary="Update status or note [admin]")
async def update_request(
    request_id: int,
    payload: UpdateOrderRequestIn,
    admin: AdminUser,
    session: DbSession,
) -> AdminOrderRequestOut:
    request = (
        await session.execute(
            select(OrderRequest)
            .where(OrderRequest.id == request_id)
            .options(
                selectinload(OrderRequest.user),
                selectinload(OrderRequest.items)
                .selectinload(OrderRequestItem.product)
                .selectinload(Product.images),
            )
        )
    ).scalar_one_or_none()
    if request is None:
        raise NotFoundError()

    if payload.status is not None:
        request.status = payload.status
    if payload.admin_note is not None:
        request.admin_note = payload.admin_note or None

    await session.commit()
    return AdminOrderRequestOut.of_admin(request)
