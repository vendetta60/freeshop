"""Cart and order-request DTOs (plan.md 6.2)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models import CartItem, OrderRequest, OrderRequestItem
from app.schemas.catalogue import ContactOut, Lang, ProductCardOut


class AddToCartIn(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1, le=99)


class SetQuantityIn(BaseModel):
    # 0 removes the line, matching the client's stepper behaviour.
    quantity: int = Field(ge=0, le=99)


class CartLineOut(BaseModel):
    id: int
    quantity: int
    line_total_minor: int
    product: ProductCardOut

    @classmethod
    def of(cls, item: CartItem, lang: Lang) -> CartLineOut:
        return cls(
            id=item.id,
            quantity=item.quantity,
            line_total_minor=item.product.price_minor * item.quantity,
            product=ProductCardOut.of(item.product, lang),
        )


class CartOut(BaseModel):
    lines: list[CartLineOut]
    total_minor: int
    item_count: int
    currency: str = "AZN"

    @classmethod
    def of(cls, items: list[CartItem], lang: Lang) -> CartOut:
        lines = [CartLineOut.of(item, lang) for item in items]
        return cls(
            lines=lines,
            total_minor=sum(line.line_total_minor for line in lines),
            item_count=sum(line.quantity for line in lines),
        )


class CreateOrderRequestIn(BaseModel):
    contact_phone: str = Field(min_length=6, max_length=24)
    contact_email: str | None = Field(default=None, max_length=255)
    note: str | None = Field(default=None, max_length=1000)


class OrderRequestItemOut(BaseModel):
    id: int
    title: str
    quantity: int
    price_minor: int
    line_total_minor: int
    product_slug: str | None
    image: str | None

    @classmethod
    def of(cls, item: OrderRequestItem) -> OrderRequestItemOut:
        product = item.product
        main = product.main_image if product else None
        return cls(
            id=item.id,
            # The snapshot, not the live product: the request must stay
            # truthful after a rename, a reprice, or a deletion (plan.md 9.1).
            title=item.title_snapshot,
            quantity=item.quantity,
            price_minor=item.price_at_request_minor,
            line_total_minor=item.price_at_request_minor * item.quantity,
            product_slug=product.slug if product and not product.is_deleted else None,
            image=main.url if main else None,
        )


class OrderRequestOut(BaseModel):
    id: int
    request_no: str
    status: str
    contact_phone: str
    contact_email: str | None
    note: str | None
    admin_note: str | None = None
    total_minor: int
    created_at: datetime
    items: list[OrderRequestItemOut]

    @classmethod
    def of(cls, request: OrderRequest, *, include_admin_note: bool = False) -> OrderRequestOut:
        return cls(
            id=request.id,
            request_no=request.request_no,
            status=request.status,
            contact_phone=request.contact_phone,
            contact_email=request.contact_email,
            note=request.note,
            admin_note=request.admin_note if include_admin_note else None,
            total_minor=request.total_minor,
            created_at=request.created_at,
            items=[OrderRequestItemOut.of(item) for item in request.items],
        )


class OrderRequestCreatedOut(BaseModel):
    """The confirmation screen needs both halves in one response: the request
    number to quote, and the channels to reach the seller on (plan.md 9.1)."""

    request: OrderRequestOut
    contact: ContactOut


class AdminOrderRequestOut(OrderRequestOut):
    user_id: int
    user_name: str | None
    user_email: str | None
    user_phone: str | None

    @classmethod
    def of_admin(cls, request: OrderRequest) -> AdminOrderRequestOut:
        base = OrderRequestOut.of(request, include_admin_note=True)
        return cls(
            **base.model_dump(),
            user_id=request.user_id,
            user_name=request.user.full_name,
            user_email=request.user.email,
            user_phone=request.user.phone,
        )


class UpdateOrderRequestIn(BaseModel):
    status: str | None = Field(default=None, pattern="^(new|viewed|completed|cancelled)$")
    admin_note: str | None = Field(default=None, max_length=2000)
