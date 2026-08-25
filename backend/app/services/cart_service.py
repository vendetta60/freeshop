"""Cart operations (plan.md 6.2, 9)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError, ErrorCode, NotFoundError
from app.db.models import CartItem, Product

MAX_QUANTITY = 99


async def load_cart(session: AsyncSession, user_id: int) -> list[CartItem]:
    """Every cart line with the data the serializer needs.

    Eager-loaded: without it, rendering a cart of N lines issues N product
    queries and N image queries.
    """
    result = await session.execute(
        select(CartItem)
        .where(CartItem.user_id == user_id)
        .options(
            selectinload(CartItem.product).selectinload(Product.images),
            selectinload(CartItem.product).selectinload(Product.category),
        )
        .order_by(CartItem.created_at)
    )
    return list(result.scalars())


async def add_item(
    session: AsyncSession, user_id: int, *, product_id: int, quantity: int
) -> CartItem:
    product = (
        await session.execute(
            # Pending and rejected listings are not addable, not just
            # unlisted: an id guessed from a moderation queue must not
            # become a cart line.
            select(Product).where(Product.id == product_id, Product.public())
        )
    ).scalar_one_or_none()

    if product is None:
        raise AppError(ErrorCode.PRODUCT_UNAVAILABLE, status_code=404)

    existing = (
        await session.execute(
            select(CartItem).where(CartItem.user_id == user_id, CartItem.product_id == product_id)
        )
    ).scalar_one_or_none()

    if existing is not None:
        # Adding again increments; it never creates a second line. The unique
        # constraint on (user_id, product_id) makes that a database guarantee.
        existing.quantity = min(MAX_QUANTITY, existing.quantity + quantity)
        await session.flush()
        return existing

    item = CartItem(user_id=user_id, product_id=product_id, quantity=min(MAX_QUANTITY, quantity))
    session.add(item)
    await session.flush()
    return item


async def set_quantity(session: AsyncSession, user_id: int, item_id: int, quantity: int) -> None:
    item = (
        await session.execute(
            select(CartItem).where(CartItem.id == item_id, CartItem.user_id == user_id)
        )
    ).scalar_one_or_none()

    # Scoped by user_id, never by id alone: otherwise anyone could edit anyone
    # else's cart by guessing an integer (plan.md 10, IDOR).
    if item is None:
        raise NotFoundError()

    if quantity <= 0:
        await session.delete(item)
    else:
        item.quantity = min(MAX_QUANTITY, quantity)
    await session.flush()


async def remove_item(session: AsyncSession, user_id: int, item_id: int) -> None:
    item = (
        await session.execute(
            select(CartItem).where(CartItem.id == item_id, CartItem.user_id == user_id)
        )
    ).scalar_one_or_none()
    if item is None:
        raise NotFoundError()
    await session.delete(item)
    await session.flush()


async def clear(session: AsyncSession, user_id: int) -> None:
    for item in await load_cart(session, user_id):
        await session.delete(item)
    await session.flush()


async def merge_guest_lines(
    session: AsyncSession, user_id: int, lines: list[tuple[int, int]]
) -> None:
    """Fold client-held lines into the server cart after sign-in.

    Used by the pending-intent replay (plan.md 9.8) and by anything that
    accumulated lines while the API was unreachable. Unknown or deleted
    products are skipped silently: failing the whole merge because one item
    went out of stock would lose the rest of the basket.
    """
    for product_id, quantity in lines:
        try:
            await add_item(session, user_id, product_id=product_id, quantity=quantity)
        except AppError:
            continue
