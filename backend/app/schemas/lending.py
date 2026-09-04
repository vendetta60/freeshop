"""Loan DTOs (FreeShop_Prompt 7)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import LoanRequest

LoanStatus = Literal["pending", "approved", "borrowed", "returned", "rejected", "cancelled"]

# What a party may ask for. `approved`, `borrowed` and `returned` are the
# owner's; `cancelled` belongs to both. The service checks the role - this
# type only keeps nonsense out of the parser.
LoanAction = Literal["approved", "rejected", "borrowed", "returned", "cancelled"]


class LoanRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int
    requested_days: Annotated[int | None, Field(default=None, ge=1, le=365)] = None
    message: Annotated[str | None, Field(default=None, max_length=1000)] = None


class LoanActionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: LoanAction
    note: Annotated[str | None, Field(default=None, max_length=1000)] = None


class LoanOut(BaseModel):
    """One loan, as either party sees it.

    `role` is resolved per request rather than stored: the same row is "my
    loan out" to one person and "my borrowed item" to the other, and shipping
    both variants would double every list on the profile page.
    """

    id: int
    product_id: int
    product_title: str
    product_slug: str
    product_image: str | None = None
    borrower_id: int
    borrower_name: str
    status: LoanStatus
    role: Literal["owner", "borrower"] | None = None
    message: str | None = None
    owner_note: str | None = None
    requested_days: int | None = None
    approved_at: datetime | None = None
    borrowed_at: datetime | None = None
    expected_return_at: datetime | None = None
    returned_at: datetime | None = None
    created_at: datetime

    @classmethod
    def of(cls, loan: LoanRequest, lang: str = "az", *, role: str | None = None) -> LoanOut:
        product = loan.product
        main = product.main_image
        borrower = loan.borrower
        return cls(
            id=loan.id,
            product_id=product.id,
            product_title=product.title(lang),
            product_slug=product.slug,
            product_image=main.url if main else None,
            borrower_id=loan.borrower_id,
            borrower_name=borrower.display_name,
            status=loan.status,
            role=role,
            message=loan.message,
            owner_note=loan.owner_note,
            requested_days=loan.requested_days,
            approved_at=loan.approved_at,
            borrowed_at=loan.borrowed_at,
            expected_return_at=loan.expected_return_at,
            returned_at=loan.returned_at,
            created_at=loan.created_at,
        )
