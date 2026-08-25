"""Cart endpoints (plan.md 6.2). Every route is scoped to the caller."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession, Lang
from app.core.errors import error_responses
from app.schemas.cart import AddToCartIn, CartOut, SetQuantityIn
from app.schemas.catalogue import Lang as LangLiteral
from app.services import cart_service

router = APIRouter(prefix="/cart", tags=["cart"], responses=error_responses(401, 404, 422))


@router.get("", summary="The signed-in user's cart")
async def read_cart(user: CurrentUser, session: DbSession, lang: Lang) -> CartOut:
    items = await cart_service.load_cart(session, user.id)
    return CartOut.of(items, cast(LangLiteral, lang))


@router.post("/items", summary="Add a product, or increment it if already present")
async def add_item(
    payload: AddToCartIn, user: CurrentUser, session: DbSession, lang: Lang
) -> CartOut:
    await cart_service.add_item(
        session, user.id, product_id=payload.product_id, quantity=payload.quantity
    )
    await session.commit()
    # Return the whole cart, not the line: the client needs the new total and
    # badge count anyway, and one round trip beats two.
    return CartOut.of(await cart_service.load_cart(session, user.id), cast(LangLiteral, lang))


@router.patch("/items/{item_id}", summary="Set a line quantity (0 removes it)")
async def set_quantity(
    item_id: int, payload: SetQuantityIn, user: CurrentUser, session: DbSession, lang: Lang
) -> CartOut:
    await cart_service.set_quantity(session, user.id, item_id, payload.quantity)
    await session.commit()
    return CartOut.of(await cart_service.load_cart(session, user.id), cast(LangLiteral, lang))


@router.delete("/items/{item_id}", summary="Remove a line")
async def remove_item(item_id: int, user: CurrentUser, session: DbSession, lang: Lang) -> CartOut:
    await cart_service.remove_item(session, user.id, item_id)
    await session.commit()
    return CartOut.of(await cart_service.load_cart(session, user.id), cast(LangLiteral, lang))


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, summary="Empty the cart")
async def clear_cart(user: CurrentUser, session: DbSession) -> None:
    await cart_service.clear(session, user.id)
    await session.commit()
