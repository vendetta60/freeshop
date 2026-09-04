"""The lifecycle of a borrowed ladder (FreeShop_Prompt 7, Rule D).

Two invariants, both enforced here and nowhere else:

  1. ONE live loan per listing. `approve` re-checks it inside the same
     transaction that writes the approval, so two owners' clicks on two
     requests cannot both win.
  2. Every state change goes through `transition`, which consults
     `LOAN_TRANSITIONS` and the actor's role. There is no setter that skips
     it - "returned" for an item that was never collected is exactly the
     nonsense an explicit table exists to refuse.

No deposits, no payments, no money of any kind (Rule G). The two people
arrange the handover themselves; what this records is who has it and when it
is due back.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError, ErrorCode, NotFoundError
from app.core.logging import get_logger
from app.db.models import LOAN_ACTIVE_STATUSES, LOAN_TRANSITIONS, LoanRequest, Product, User
from app.services import messaging_service, notification_service

log = get_logger(__name__)

LOAN_RELATIONS = (
    selectinload(LoanRequest.product).selectinload(Product.images),
    selectinload(LoanRequest.borrower),
)

DEFAULT_BORROW_DAYS = 7

# A loan due back within this window is worth a nudge (FreeShop_Prompt 12).
DUE_SOON_DAYS = 2

# Who is allowed to drive each transition. `owner` is the person who lent the
# thing; `borrower` is the person who has it.
#
# Cancelling is open to both on purpose: either party can change their mind
# before the handover, and forcing the borrower to ask the owner to cancel is
# how a request sits pending forever.
ACTORS: dict[tuple[str, str], tuple[str, ...]] = {
    ("pending", "approved"): ("owner",),
    ("pending", "rejected"): ("owner",),
    ("pending", "cancelled"): ("owner", "borrower"),
    ("approved", "borrowed"): ("owner",),
    ("approved", "cancelled"): ("owner", "borrower"),
    # Only the owner confirms a return: they are the one who has to be
    # holding the thing for it to be true.
    ("borrowed", "returned"): ("owner",),
}


async def load(session: AsyncSession, loan_id: int) -> LoanRequest:
    loan = (
        await session.execute(
            select(LoanRequest).where(LoanRequest.id == loan_id).options(*LOAN_RELATIONS)
        )
    ).scalar_one_or_none()
    if loan is None:
        raise NotFoundError()
    return loan


def role_of(loan: LoanRequest, user: User) -> str | None:
    if user.id == loan.borrower_id:
        return "borrower"
    if user.id == loan.product.owner_id:
        return "owner"
    return None


async def active_loan(session: AsyncSession, product_id: int) -> LoanRequest | None:
    """The loan currently holding this listing, if any."""
    return (
        await session.execute(
            select(LoanRequest)
            .where(
                LoanRequest.product_id == product_id,
                LoanRequest.status.in_(LOAN_ACTIVE_STATUSES),
            )
            .options(*LOAN_RELATIONS)
        )
    ).scalar_one_or_none()


async def listing_state(session: AsyncSession, product: Product) -> str:
    """ "available" | "reserved" | "borrowed" - derived, never stored.

    Storing it on the product would create a second copy of the truth, and
    the copy is always the one that goes stale (see lending.py).
    """
    if not product.is_loan:
        return "available"
    live = await active_loan(session, product.id)
    if live is None:
        return "available"
    return "borrowed" if live.status == "borrowed" else "reserved"


async def listing_states(session: AsyncSession, product_ids: list[int]) -> dict[int, str]:
    """The same answer for a whole page, in one query.

    Exists because a list of twenty loan listings must not become twenty
    `listing_state` calls - the N+1 that plan.md 11 makes a build blocker.
    """
    if not product_ids:
        return {}
    rows = await session.execute(
        select(LoanRequest.product_id, LoanRequest.status).where(
            LoanRequest.product_id.in_(product_ids),
            LoanRequest.status.in_(LOAN_ACTIVE_STATUSES),
        )
    )
    states: dict[int, str] = {}
    for product_id, status in rows.all():
        # `borrowed` outranks `reserved` if both somehow exist.
        if status == "borrowed" or product_id not in states:
            states[product_id] = "borrowed" if status == "borrowed" else "reserved"
    return states


# ---------------------------------------------------------------------------
# Requesting
# ---------------------------------------------------------------------------
async def request_loan(
    session: AsyncSession,
    *,
    product: Product,
    borrower: User,
    requested_days: int | None,
    message: str | None,
) -> LoanRequest:
    if not product.is_loan:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            status_code=409,
            field="product_id",
            details={"reason": "not_a_loan"},
        )
    if product.owner_id == borrower.id:
        raise AppError(
            ErrorCode.VALIDATION_ERROR, status_code=409, details={"reason": "own_listing"}
        )

    now = datetime.now(UTC)
    if product.available_until is not None and product.available_until < now:
        raise AppError(
            ErrorCode.PRODUCT_UNAVAILABLE, status_code=409, details={"reason": "window_closed"}
        )

    # Asking twice while the first ask is still live would give the owner two
    # identical rows to choose between.
    duplicate = (
        await session.execute(
            select(LoanRequest).where(
                LoanRequest.product_id == product.id,
                LoanRequest.borrower_id == borrower.id,
                LoanRequest.status.in_(("pending", *LOAN_ACTIVE_STATUSES)),
            )
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            status_code=409,
            details={"reason": "already_requested", "loan_id": duplicate.id},
        )

    days = requested_days or product.max_borrow_days or DEFAULT_BORROW_DAYS
    if product.max_borrow_days is not None and days > product.max_borrow_days:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            status_code=422,
            field="requested_days",
            details={"reason": "over_max", "max": product.max_borrow_days},
        )

    loan = LoanRequest(
        product_id=product.id,
        borrower_id=borrower.id,
        status="pending",
        message=(message or "").strip() or None,
        requested_days=days,
    )
    session.add(loan)
    await session.flush()

    await notification_service.notify(
        session,
        user_id=product.owner_id,
        actor_id=borrower.id,
        kind="loan_requested",
        link=f"/profile/loans/{loan.id}",
        loan_id=loan.id,
        title=product.title_az,
    )

    await session.refresh(loan, ["product", "borrower"])
    log.info("loan_requested", loan_id=loan.id, product_id=product.id, borrower_id=borrower.id)
    return loan


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
async def transition(
    session: AsyncSession,
    loan: LoanRequest,
    *,
    to: str,
    actor: User,
    note: str | None = None,
) -> LoanRequest:
    """The only way a loan changes state."""
    role = role_of(loan, actor)
    if role is None:
        # Not a party to this loan. 404 rather than 403 for the same reason
        # the messaging gate does it.
        raise NotFoundError()

    allowed = LOAN_TRANSITIONS.get(loan.status, ())
    if to not in allowed:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            status_code=409,
            field="status",
            details={"reason": "invalid_transition", "from": loan.status, "allowed": list(allowed)},
        )
    if role not in ACTORS.get((loan.status, to), ()):
        raise AppError(
            ErrorCode.FORBIDDEN,
            status_code=403,
            details={"reason": "wrong_party", "role": role},
        )

    now = datetime.now(UTC)

    if to == "approved":
        # Re-checked here, inside the writing transaction: between the owner
        # loading the page and clicking, they may already have approved
        # somebody else.
        live = await active_loan(session, loan.product_id)
        if live is not None and live.id != loan.id:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                status_code=409,
                details={"reason": "already_lent", "loan_id": live.id},
            )
        loan.approved_at = now
        loan.expected_return_at = now + timedelta(days=loan.requested_days or DEFAULT_BORROW_DAYS)

    elif to == "borrowed":
        loan.borrowed_at = now
        # The clock starts at the handover, not at the approval: an item
        # approved on Monday and collected on Friday is not already overdue.
        loan.expected_return_at = now + timedelta(days=loan.requested_days or DEFAULT_BORROW_DAYS)

    elif to == "returned":
        loan.returned_at = now

    elif to in ("cancelled", "rejected"):
        loan.cancelled_at = now

    loan.status = to
    if note is not None:
        loan.owner_note = note.strip() or None

    await _announce(session, loan, to=to, actor=actor)
    await session.flush()
    await session.refresh(loan, ["product", "borrower"])
    log.info("loan_transition", loan_id=loan.id, to=to, actor_id=actor.id)
    return loan


async def _announce(session: AsyncSession, loan: LoanRequest, *, to: str, actor: User) -> None:
    """Tell the other party, and open the thread they will need.

    Approval is the moment two strangers have to arrange a doorstep, so the
    conversation is created here rather than waiting for one of them to find
    the button (FreeShop_Prompt 3).
    """
    owner_id = loan.product.owner_id
    other_id = owner_id if actor.id == loan.borrower_id else loan.borrower_id

    kinds = {
        "approved": "loan_approved",
        "returned": "loan_returned",
    }
    if to in kinds:
        await notification_service.notify(
            session,
            user_id=other_id,
            actor_id=actor.id,
            kind=kinds[to],
            link=f"/profile/loans/{loan.id}",
            loan_id=loan.id,
            title=loan.product.title_az,
        )

    if to == "approved":
        await messaging_service.system_thread(
            session,
            kind="loan",
            context_id=loan.id,
            user_ids=(owner_id, loan.borrower_id),
        )


async def due_soon(session: AsyncSession, *, within_days: int = DUE_SOON_DAYS) -> list[LoanRequest]:
    """Borrowed items coming back shortly.

    Read by the borrower's own dashboard rather than pushed by a scheduler:
    there is no job runner in this deployment (plan.md 12.3), and a reminder
    nobody is awake to send is not a reminder.
    """
    horizon = datetime.now(UTC) + timedelta(days=within_days)
    rows = await session.execute(
        select(LoanRequest)
        .where(
            LoanRequest.status == "borrowed",
            LoanRequest.expected_return_at.is_not(None),
            LoanRequest.expected_return_at <= horizon,
        )
        .options(*LOAN_RELATIONS)
        .order_by(LoanRequest.expected_return_at.asc())
    )
    return list(rows.scalars())


async def for_borrower(session: AsyncSession, user_id: int) -> list[LoanRequest]:
    rows = await session.execute(
        select(LoanRequest)
        .where(LoanRequest.borrower_id == user_id)
        .options(*LOAN_RELATIONS)
        .order_by(LoanRequest.created_at.desc())
    )
    return list(rows.scalars())


async def for_owner(session: AsyncSession, user_id: int) -> list[LoanRequest]:
    rows = await session.execute(
        select(LoanRequest)
        .join(Product, Product.id == LoanRequest.product_id)
        .where(Product.owner_id == user_id)
        .options(*LOAN_RELATIONS)
        .order_by(LoanRequest.created_at.desc())
    )
    return list(rows.scalars())
