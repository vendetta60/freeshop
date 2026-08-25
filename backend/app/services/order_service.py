"""Turning a cart into an order request (plan.md 9.1).

This is the payoff of the whole product: no payment, no checkout - the cart
becomes a contact request that reaches the seller.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger
from app.db.models import OrderRequest, OrderRequestItem, Product, User
from app.schemas.catalogue import ContactOut
from app.services import cart_service

log = get_logger(__name__)

# A repeat submission within this window returns the original request rather
# than creating a duplicate (plan.md 6.1).
IDEMPOTENCY_WINDOW = timedelta(minutes=10)


async def _allocate_request_no(session: AsyncSession) -> str:
    """Human-readable and sequential per year: SR-2026-0041.

    The admin needs something to quote on the phone; a database id is
    forgettable and leaks how many requests exist.

    MAX+1 is safe here because SQLite serialises writes and this runs inside
    the submitting transaction. On PostgreSQL this becomes a sequence.
    """
    settings = get_settings()
    year = datetime.now(UTC).year
    prefix = f"{settings.request_prefix}-{year}-"

    highest = (
        await session.execute(
            select(func.max(OrderRequest.request_no)).where(
                OrderRequest.request_no.like(f"{prefix}%")
            )
        )
    ).scalar_one_or_none()

    next_number = 1
    if highest:
        try:
            next_number = int(highest.rsplit("-", 1)[1]) + 1
        except (IndexError, ValueError):
            # A malformed row must not stop new requests being taken.
            log.warning("request_no_unparseable", value=highest)

    return f"{prefix}{next_number:04d}"


async def seller_contact(session: AsyncSession, lang: str) -> ContactOut:
    """Kept as a re-export so the request flow reads as one story; the field
    mapping itself lives with the settings that produce it."""
    from app.services import settings_service

    return await settings_service.contact(session, lang)


async def _existing_for_key(session: AsyncSession, user_id: int, key: str) -> OrderRequest | None:
    since = datetime.now(UTC) - IDEMPOTENCY_WINDOW
    return (
        await session.execute(
            select(OrderRequest)
            .where(
                OrderRequest.user_id == user_id,
                OrderRequest.idempotency_key == key,
                OrderRequest.created_at >= since,
            )
            .options(
                selectinload(OrderRequest.items)
                .selectinload(OrderRequestItem.product)
                .selectinload(Product.images)
            )
        )
    ).scalar_one_or_none()


async def create_from_cart(
    session: AsyncSession,
    user: User,
    *,
    contact_phone: str,
    contact_email: str | None,
    note: str | None,
    idempotency_key: str | None = None,
) -> tuple[OrderRequest, bool]:
    """Snapshot the cart into a request and clear it. Returns (request, created).

    One transaction, in this order on purpose:
      1. read the cart
      2. reject an empty cart
      3. reject unavailable products, naming them
      4. snapshot title and price per line
      5. allocate the number
      6. clear the cart

    The snapshot is the important part: prices and titles are copied, so the
    request stays truthful after the product is renamed, repriced or deleted.
    """
    if idempotency_key:
        duplicate = await _existing_for_key(session, user.id, idempotency_key)
        if duplicate is not None:
            # A double-tapped button, or a retried request after a dropped
            # response. Returning the original beats creating a second one.
            return duplicate, False

    items = await cart_service.load_cart(session, user.id)
    if not items:
        raise AppError(ErrorCode.CART_EMPTY, status_code=409)

    unavailable = [
        item.product.slug
        for item in items
        if item.product is None or not item.product.is_publicly_visible
    ]
    if unavailable:
        raise AppError(
            ErrorCode.PRODUCT_UNAVAILABLE,
            status_code=409,
            details={"products": unavailable},
        )

    request = OrderRequest(
        request_no=await _allocate_request_no(session),
        user_id=user.id,
        status="new",
        contact_phone=contact_phone,
        contact_email=contact_email,
        note=note,
        total_minor=0,
        idempotency_key=idempotency_key,
    )
    session.add(request)
    await session.flush()

    total = 0
    for item in items:
        product: Product = item.product
        total += product.price_minor * item.quantity
        session.add(
            OrderRequestItem(
                order_request_id=request.id,
                product_id=product.id,
                title_snapshot=product.title_az,
                quantity=item.quantity,
                price_at_request_minor=product.price_minor,
            )
        )

    request.total_minor = total
    await cart_service.clear(session, user.id)
    await session.flush()

    log.info(
        "order_request_created",
        request_no=request.request_no,
        user_id=user.id,
        lines=len(items),
        total_minor=total,
    )

    # Re-read with relations loaded. The items were added to the session, not
    # appended to request.items, so serialising would trigger a lazy load -
    # which in async SQLAlchemy raises MissingGreenlet instead of quietly
    # issuing a query.
    return await load_one(session, request.id), True


async def load_one(session: AsyncSession, request_id: int) -> OrderRequest:
    """A request with everything the serializer touches."""
    return (
        await session.execute(
            select(OrderRequest)
            .where(OrderRequest.id == request_id)
            .options(
                selectinload(OrderRequest.items)
                .selectinload(OrderRequestItem.product)
                .selectinload(Product.images)
            )
        )
    ).scalar_one()


async def load_for_user(
    session: AsyncSession, user_id: int, *, limit: int = 50
) -> list[OrderRequest]:
    result = await session.execute(
        select(OrderRequest)
        .where(OrderRequest.user_id == user_id)
        .options(
            selectinload(OrderRequest.items)
            .selectinload(OrderRequestItem.product)
            .selectinload(Product.images)
        )
        .order_by(OrderRequest.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())
