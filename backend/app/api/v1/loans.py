"""Borrowing and lending endpoints (FreeShop_Prompt 7, Rule D)."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, DbSession, Lang, VerifiedUser
from app.core.errors import error_responses
from app.schemas.lending import LoanActionIn, LoanOut, LoanRequestIn
from app.services import catalogue_service, loan_service

router = APIRouter(
    prefix="/loans", tags=["loans"], responses=error_responses(401, 403, 404, 409, 422)
)

NO_STORE = {"Cache-Control": "no-store"}


@router.get("/mine", summary="Items you have borrowed or asked to borrow")
async def my_borrowings(
    user: CurrentUser, session: DbSession, lang: Lang, response: Response
) -> list[LoanOut]:
    response.headers.update(NO_STORE)
    loans = await loan_service.for_borrower(session, user.id)
    return [LoanOut.of(loan, lang, role="borrower") for loan in loans]


@router.get("/lent", summary="Items you have lent out")
async def my_lendings(
    user: CurrentUser, session: DbSession, lang: Lang, response: Response
) -> list[LoanOut]:
    response.headers.update(NO_STORE)
    loans = await loan_service.for_owner(session, user.id)
    return [LoanOut.of(loan, lang, role="owner") for loan in loans]


@router.post("", status_code=status.HTTP_201_CREATED, summary="Ask to borrow a listing")
async def request_loan(
    payload: LoanRequestIn, user: VerifiedUser, session: DbSession, lang: Lang
) -> LoanOut:
    """The phone gate applies (plan.md 9.3).

    Borrowing is a promise to give somebody's property back, which is a
    heavier commitment than asking for something they were giving away
    anyway - so the same verified number the giver had to prove is required
    of the borrower.
    """
    product = await catalogue_service.load_product(session, payload.product_id)
    loan = await loan_service.request_loan(
        session,
        product=product,
        borrower=user,
        requested_days=payload.requested_days,
        message=payload.message,
    )
    await session.commit()
    return LoanOut.of(loan, lang, role="borrower")


@router.get("/{loan_id}", summary="One loan")
async def get_loan(
    loan_id: int, user: CurrentUser, session: DbSession, lang: Lang, response: Response
) -> LoanOut:
    """Visible to the two parties and nobody else - a stranger gets a 404."""
    response.headers.update(NO_STORE)
    loan = await loan_service.load(session, loan_id)
    role = loan_service.role_of(loan, user)
    if role is None:
        from app.core.errors import NotFoundError

        raise NotFoundError()
    return LoanOut.of(loan, lang, role=role)


@router.post("/{loan_id}/status", summary="Approve, reject, hand over, return or cancel")
async def change_status(
    loan_id: int, payload: LoanActionIn, user: CurrentUser, session: DbSession, lang: Lang
) -> LoanOut:
    """The single door into the lifecycle.

    One endpoint rather than five verbs, because the rules that matter -
    which transitions exist and who may make them - live in one table in
    `loan_service`, and five endpoints would be five chances to check them
    slightly differently.
    """
    loan = await loan_service.load(session, loan_id)
    updated = await loan_service.transition(
        session, loan, to=payload.status, actor=user, note=payload.note
    )
    await session.commit()
    return LoanOut.of(updated, lang, role=loan_service.role_of(updated, user))
