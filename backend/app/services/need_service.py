"""Needs: the reverse side of the board (FreeShop_Prompt 4, 5).

Two things live here that are easy to get wrong anywhere else:

  * A need is `pending` until an administrator reads it, exactly like a
    listing (plan.md D25). Same queue, same vocabulary, same fail-closed
    default - a new code path that forgets to set a moderation status
    publishes nothing.

  * Converting a disappointed requester into visible demand (Rule C) is
    DEDUPLICATED. Somebody who misses out on four ladders in a month should
    end up with one need, not four, or the aggregate count that the whole
    feature exists to produce becomes a lie.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError, ErrorCode, NotFoundError
from app.core.logging import get_logger
from app.core.text import normalise_search
from app.db.models import NeedRequest, OrderRequestItem, Product, User
from app.services import geo, notification_service

log = get_logger(__name__)

NEED_RELATIONS = (selectinload(NeedRequest.category), selectinload(NeedRequest.user))

# A need that nobody has touched stops being true eventually. Not deleted -
# `expired` keeps it in the owner's list with a reason, which "it vanished"
# does not.
DEFAULT_TTL_DAYS = 90

# Which lifecycle transitions the OWNER may make. The administrator's
# moderation status is a separate axis and is not in this table.
OWNER_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "open": ("partially_fulfilled", "fulfilled", "closed"),
    "partially_fulfilled": ("fulfilled", "closed", "open"),
    "fulfilled": ("open",),
    "closed": ("open",),
    "expired": ("open",),
}


async def load(session: AsyncSession, need_id: int) -> NeedRequest:
    need = (
        await session.execute(
            select(NeedRequest).where(NeedRequest.id == need_id).options(*NEED_RELATIONS)
        )
    ).scalar_one_or_none()
    if need is None:
        raise NotFoundError()
    return need


async def load_public(session: AsyncSession, need_id: int) -> NeedRequest:
    """A need as a visitor may see it.

    A pending or rejected need is a 404, not a 403: confirming that id 41
    exists but is hidden tells a stranger something about somebody's
    circumstances that they did not publish.
    """
    need = (
        await session.execute(
            select(NeedRequest)
            .where(NeedRequest.id == need_id, NeedRequest.public())
            .options(*NEED_RELATIONS)
        )
    ).scalar_one_or_none()
    if need is None:
        raise NotFoundError()
    return need


async def create(
    session: AsyncSession,
    data: dict[str, Any],
    *,
    user: User,
    source_order_item_id: int | None = None,
) -> NeedRequest:
    """Post a need. Lands in the moderation queue.

    The location falls back to the poster's saved default, because the most
    common case by far is "I need this, where I live" and asking again is
    friction for no information (FreeShop_Prompt 1).
    """
    need = NeedRequest(
        user_id=user.id,
        title=data["title"].strip(),
        description=(data.get("description") or "").strip(),
        category_id=data.get("category_id"),
        quantity_needed=data.get("quantity_needed") or 1,
        status="open",
        moderation_status="pending",
        expires_at=datetime.now(UTC) + timedelta(days=DEFAULT_TTL_DAYS),
        source_order_item_id=source_order_item_id,
    )

    if data.get("city"):
        geo.apply_to(need, data)
    else:
        geo.copy_from(need, user)

    need.refresh_search_text()
    session.add(need)
    await session.flush()
    await session.refresh(need, ["category", "user"])
    return need


async def update(session: AsyncSession, need: NeedRequest, data: dict[str, Any]) -> NeedRequest:
    """Edit your own open need.

    An edit does NOT send it back to the queue, matching how listings behave
    (catalogue_service.moderate_product): making somebody re-queue to fix a
    typo is how a moderated board stops being used.
    """
    if need.status in ("fulfilled", "closed"):
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            status_code=409,
            field="status",
            details={"reason": "need_not_editable"},
        )

    if data.get("title"):
        need.title = data["title"].strip()
    if "description" in data:
        need.description = (data.get("description") or "").strip()
    if "category_id" in data:
        need.category_id = data["category_id"]
    if data.get("quantity_needed") is not None:
        need.quantity_needed = data["quantity_needed"]
    if data.get("city"):
        geo.apply_to(need, data)

    need.refresh_search_text()
    await session.flush()
    await session.refresh(need, ["category", "user"])
    return need


async def set_status(session: AsyncSession, need: NeedRequest, status: str) -> NeedRequest:
    """Owner-driven lifecycle, through the transition table only."""
    allowed = OWNER_TRANSITIONS.get(need.status, ())
    if status not in allowed:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            status_code=409,
            field="status",
            details={"reason": "invalid_transition", "from": need.status, "allowed": list(allowed)},
        )
    need.status = status
    if status == "open":
        # Reopening restarts the clock; an expiry date in the past would put
        # it straight back where it came from.
        need.expires_at = datetime.now(UTC) + timedelta(days=DEFAULT_TTL_DAYS)
    await session.flush()
    await session.refresh(need, ["category", "user"])
    return need


async def moderate(
    session: AsyncSession, need: NeedRequest, *, status: str, note: str | None = None
) -> NeedRequest:
    """Approve or reject, mirroring catalogue_service.moderate_product."""
    if status not in ("approved", "rejected"):
        raise AppError(ErrorCode.VALIDATION_ERROR, status_code=422, field="status")

    need.moderation_status = status
    need.moderation_note = (note or "").strip() or None
    need.reviewed_at = datetime.now(UTC)

    await notification_service.notify(
        session,
        user_id=need.user_id,
        kind="need_approved" if status == "approved" else "need_rejected",
        link=f"/needs/{need.id}" if status == "approved" else "/profile/needs",
        need_id=need.id,
        title=need.title,
    )

    await session.flush()
    await session.refresh(need, ["category", "user"])
    return need


async def expire_stale(session: AsyncSession) -> int:
    """Mark needs whose date has passed. Returns how many changed.

    Called from the needs list endpoint rather than from a scheduler: this
    deployment has no job runner (plan.md 12.3), and the alternative -
    filtering expired rows out at read time without ever writing the status -
    would leave the owner's own list claiming the need is still open.
    """
    now = datetime.now(UTC)
    rows = await session.execute(
        select(NeedRequest).where(
            NeedRequest.status.in_(("open", "partially_fulfilled")),
            NeedRequest.expires_at.is_not(None),
            NeedRequest.expires_at < now,
        )
    )
    stale = list(rows.scalars())
    for need in stale:
        need.status = "expired"
    if stale:
        log.info("needs_expired", count=len(stale))
    return len(stale)


# ---------------------------------------------------------------------------
# Turning an unsuccessful listing request into demand (FreeShop_Prompt 5)
# ---------------------------------------------------------------------------
async def find_duplicate(
    session: AsyncSession, *, user_id: int, title: str, category_id: int | None
) -> NeedRequest | None:
    """An open need this person already has for the same thing.

    Matched on the FOLDED title so "Nərdivan" and "nerdivan" are one need,
    and on the category so two genuinely different things with similar names
    stay apart.
    """
    folded = normalise_search(title)
    if not folded:
        return None

    rows = await session.execute(
        select(NeedRequest).where(
            NeedRequest.user_id == user_id,
            NeedRequest.open_states(),
        )
    )
    for existing in rows.scalars():
        if normalise_search(existing.title) != folded:
            continue
        if category_id is not None and existing.category_id not in (None, category_id):
            continue
        return existing
    return None


async def from_order_item(
    session: AsyncSession, item: OrderRequestItem, *, user: User
) -> tuple[NeedRequest, bool]:
    """ "Keep this as a need" (Rule C). Returns (need, created).

    Only offered for a line that actually lost: converting a pending or a
    successful request would either pre-empt the giver's decision or claim
    somebody still needs what they have just been given.

    Idempotent by design. Clicking twice, or missing out on the same item
    twice, produces ONE need - the aggregate demand count is the product of
    this function and it has to be trustworthy (Rule F).
    """
    if item.outcome != "not_selected":
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            status_code=409,
            field="outcome",
            details={"reason": "request_not_resolved"},
        )

    title = item.title_snapshot
    category_id: int | None = None
    product: Product | None = item.product
    if product is not None:
        category_id = product.category_id

    existing = await find_duplicate(session, user_id=user.id, title=title, category_id=category_id)
    if existing is not None:
        # Point the existing need at this disappointment too, so the origin
        # trail survives even though no second row was created.
        if existing.source_order_item_id is None:
            existing.source_order_item_id = item.id
        await session.flush()
        return existing, False

    need = await create(
        session,
        {
            "title": title,
            "description": "",
            "category_id": category_id,
            "quantity_needed": item.quantity,
            # Inherit the listing's location when there is one: the person
            # asked for something in that place, which is better evidence of
            # where they can collect from than a profile they may never have
            # filled in.
            "city": (product.city if product is not None else None) or user.city,
            "district": (product.district if product is not None else None) or user.district,
        },
        user=user,
        source_order_item_id=item.id,
    )
    log.info("need_from_order_item", need_id=need.id, item_id=item.id, user_id=user.id)
    return need, True
