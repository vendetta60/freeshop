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
from app.core.errors import AppError, ErrorCode, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.db.models import NeedRequest, OrderRequest, OrderRequestItem, Product, User
from app.schemas.catalogue import ContactOut
from app.services import cart_service, notification_service

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


# ---------------------------------------------------------------------------
# Choosing a recipient, and what happens to everyone else (FreeShop_Prompt 5)
# ---------------------------------------------------------------------------
async def requesters_for(session: AsyncSession, product_id: int) -> list[OrderRequestItem]:
    """Every undecided ask for one listing, oldest first.

    Oldest first because that is the order a giver is most likely to consider
    fair, and because a list sorted newest-first quietly rewards whoever
    refreshed the page most recently.
    """
    rows = await session.execute(
        select(OrderRequestItem)
        .where(OrderRequestItem.product_id == product_id, OrderRequestItem.outcome == "pending")
        .options(selectinload(OrderRequestItem.order_request).selectinload(OrderRequest.user))
        .order_by(OrderRequestItem.created_at.asc())
    )
    return list(rows.scalars())


async def hand_over(
    session: AsyncSession, *, product: Product, chosen_item_id: int, owner: User
) -> tuple[OrderRequestItem, list[OrderRequestItem]]:
    """The giver picks one person. Returns (winner, everyone_else).

    THIS IS THE HEART OF Rule C. Ten people asked; one receives. The other
    nine are NOT deleted and NOT hidden - they are marked `not_selected`,
    which is what makes them eligible to become visible local demand if their
    owner consents (services/need_service.from_order_item).

    Consent is the reason this function does not create the needs itself. It
    marks the outcome and notifies; turning a disappointment into a public
    post is the requester's decision to make, not the giver's and not ours.
    """
    if product.owner_id != owner.id:
        raise ForbiddenError()

    pending = await requesters_for(session, product.id)
    winner = next((item for item in pending if item.id == chosen_item_id), None)
    if winner is None:
        raise NotFoundError()

    now = datetime.now(UTC)
    winner.outcome = "received"
    winner.decided_at = now
    winner.order_request.status = "completed"

    await notification_service.notify(
        session,
        user_id=winner.order_request.user_id,
        actor_id=owner.id,
        kind="request_accepted",
        link=f"/profile/orders/{winner.order_request_id}",
        product_id=product.id,
        title=product.title_az,
    )

    others = [item for item in pending if item.id != winner.id]
    for item in others:
        item.outcome = "not_selected"
        item.decided_at = now
        await notification_service.notify(
            session,
            user_id=item.order_request.user_id,
            actor_id=owner.id,
            kind="request_not_selected",
            link=f"/profile/orders/{item.order_request_id}",
            product_id=product.id,
            item_id=item.id,
            title=product.title_az,
        )

    # The listing itself is spoken for. A give-away that has been given away
    # must stop appearing as available, or the next nine people ask for it too.
    if not product.is_loan:
        product.stock_status = "out_of_stock"

    await session.flush()
    log.info(
        "listing_handed_over",
        product_id=product.id,
        winner_item_id=winner.id,
        not_selected=len(others),
    )
    return winner, others


async def convertible_items(session: AsyncSession, user_id: int) -> list[OrderRequestItem]:
    """Lines this person lost that have not yet become a need.

    Drives the "Bu əşyanı ala bilmədiniz" prompt. A line whose need already
    exists is excluded, so the prompt does not keep reappearing after it has
    been answered.
    """
    rows = await session.execute(
        select(OrderRequestItem)
        .join(OrderRequest, OrderRequest.id == OrderRequestItem.order_request_id)
        .outerjoin(NeedRequest, NeedRequest.source_order_item_id == OrderRequestItem.id)
        .where(
            OrderRequest.user_id == user_id,
            OrderRequestItem.outcome == "not_selected",
            NeedRequest.id.is_(None),
        )
        .options(selectinload(OrderRequestItem.product))
        .order_by(OrderRequestItem.decided_at.desc())
    )
    return list(rows.scalars())
