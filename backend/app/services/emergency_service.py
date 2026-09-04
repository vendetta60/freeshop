"""Community aid cases and the offers against them (FreeShop_Prompt 8).

The counters on an item (`quantity_committed`, `quantity_received`) are
DERIVED. `recount` recomputes them from the commitments after every change
rather than incrementing them in place, because an increment that runs twice,
or fails halfway, leaves a public progress figure that is quietly wrong - and
"3 of 2 blankets received" is the kind of wrong that makes people stop
trusting the whole page.

Nothing here touches money (Rule G). A commitment is a promise to bring an
object; the platform records it and gets out of the way.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError, ErrorCode, NotFoundError
from app.core.logging import get_logger
from app.core.text import slugify
from app.db.models import (
    COMMITMENT_TRANSITIONS,
    AidCommitment,
    EmergencyAidCase,
    EmergencyAidItem,
    User,
)
from app.services import geo, notification_service

log = get_logger(__name__)

CASE_RELATIONS = (selectinload(EmergencyAidCase.items),)

# Which case statuses an administrator may move between. `draft -> active` is
# publishing; there is no path back to draft, because a case that has been
# seen by the community cannot be un-seen.
CASE_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "draft": ("active", "cancelled"),
    "active": ("paused", "completed", "cancelled"),
    "paused": ("active", "completed", "cancelled"),
    "completed": (),
    "cancelled": (),
}


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------
async def load(session: AsyncSession, case_id: int) -> EmergencyAidCase:
    case = (
        await session.execute(
            select(EmergencyAidCase)
            .where(EmergencyAidCase.id == case_id)
            .options(selectinload(EmergencyAidCase.items).selectinload(EmergencyAidItem.category))
        )
    ).scalar_one_or_none()
    if case is None:
        raise NotFoundError()
    return case


async def load_public(session: AsyncSession, key: str | int) -> EmergencyAidCase:
    """By id or slug, and only if the public may see it.

    A draft case is a 404. It describes a real family's misfortune before
    anyone has agreed it should be public, and guessing an id must not be a
    way to read it early.
    """
    stmt = select(EmergencyAidCase).options(
        selectinload(EmergencyAidCase.items).selectinload(EmergencyAidItem.category)
    )
    stmt = (
        stmt.where(EmergencyAidCase.id == int(key))
        if str(key).isdigit()
        else stmt.where(EmergencyAidCase.slug == str(key))
    )
    case = (await session.execute(stmt)).scalar_one_or_none()
    if case is None or not case.is_public:
        raise NotFoundError()
    return case


async def create_case(
    session: AsyncSession, data: dict[str, Any], *, admin: User
) -> EmergencyAidCase:
    """Only ever called from an admin route (Rule E).

    Created as a `draft`. Publishing is a second, separate decision, so a
    half-written case cannot appear on the home page because somebody hit
    save while thinking.
    """
    from app.services import catalogue_service

    case = EmergencyAidCase(
        slug=await catalogue_service.unique_slug(session, EmergencyAidCase, data["title_az"]),
        title_az=data["title_az"].strip(),
        title_en=(data.get("title_en") or "").strip() or None,
        description_az=(data.get("description_az") or "").strip(),
        description_en=(data.get("description_en") or "").strip() or None,
        beneficiary_display_name=(data.get("beneficiary_display_name") or "").strip() or None,
        verification_note_internal=(data.get("verification_note_internal") or "").strip() or None,
        status="draft",
        created_by_admin_id=admin.id,
    )
    geo.apply_to(case, data)
    session.add(case)
    await session.flush()
    await session.refresh(case, ["items"])
    log.info("aid_case_created", case_id=case.id, admin_id=admin.id)
    return case


async def update_case(
    session: AsyncSession, case: EmergencyAidCase, data: dict[str, Any]
) -> EmergencyAidCase:
    for field in ("title_az", "description_az"):
        if data.get(field) is not None:
            setattr(case, field, data[field].strip())
    for field in ("title_en", "description_en", "beneficiary_display_name"):
        if field in data:
            setattr(case, field, (data.get(field) or "").strip() or None)
    if "verification_note_internal" in data:
        case.verification_note_internal = (
            data.get("verification_note_internal") or ""
        ).strip() or None
    if data.get("city"):
        geo.apply_to(case, data)
    if data.get("title_az"):
        case.slug = slugify(case.title_az) or case.slug

    await session.flush()
    await session.refresh(case, ["items"])
    return case


async def set_case_status(
    session: AsyncSession, case: EmergencyAidCase, status: str
) -> EmergencyAidCase:
    allowed = CASE_TRANSITIONS.get(case.status, ())
    if status not in allowed:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            status_code=409,
            field="status",
            details={"reason": "invalid_transition", "from": case.status, "allowed": list(allowed)},
        )

    now = datetime.now(UTC)
    if status == "active" and case.published_at is None:
        case.published_at = now
    if status in ("completed", "cancelled"):
        case.closed_at = now

    case.status = status
    await session.flush()
    await session.refresh(case, ["items"])
    log.info("aid_case_status", case_id=case.id, status=status)
    return case


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------
async def add_item(
    session: AsyncSession, case: EmergencyAidCase, data: dict[str, Any]
) -> EmergencyAidItem:
    item = EmergencyAidItem(
        emergency_case_id=case.id,
        title_az=data["title_az"].strip(),
        title_en=(data.get("title_en") or "").strip() or None,
        category_id=data.get("category_id"),
        quantity_needed=data.get("quantity_needed") or 1,
        priority=data.get("priority") or "normal",
        notes=(data.get("notes") or "").strip() or None,
        sort_order=data.get("sort_order") or len(case.items),
    )
    session.add(item)
    await session.flush()
    await session.refresh(case, ["items"])
    return item


async def load_item(session: AsyncSession, item_id: int) -> EmergencyAidItem:
    item = (
        await session.execute(
            select(EmergencyAidItem)
            .where(EmergencyAidItem.id == item_id)
            .options(selectinload(EmergencyAidItem.case))
        )
    ).scalar_one_or_none()
    if item is None:
        raise NotFoundError()
    return item


async def update_item(
    session: AsyncSession, item: EmergencyAidItem, data: dict[str, Any]
) -> EmergencyAidItem:
    if data.get("title_az"):
        item.title_az = data["title_az"].strip()
    if "title_en" in data:
        item.title_en = (data.get("title_en") or "").strip() or None
    if "category_id" in data:
        item.category_id = data["category_id"]
    if data.get("quantity_needed") is not None:
        item.quantity_needed = data["quantity_needed"]
    if data.get("priority"):
        item.priority = data["priority"]
    if "notes" in data:
        item.notes = (data.get("notes") or "").strip() or None
    if data.get("sort_order") is not None:
        item.sort_order = data["sort_order"]
    await session.flush()
    return item


async def recount(session: AsyncSession, item_id: int) -> None:
    """Recompute an item's two derived counters from its commitments.

    `committed` counts what is promised AND not yet delivered plus what has
    arrived - i.e. everything still expected. Cancelled offers count for
    nothing, which is the point of letting people cancel.
    """
    rows = await session.execute(
        select(AidCommitment.status, func.sum(AidCommitment.quantity))
        .where(AidCommitment.item_id == item_id)
        .group_by(AidCommitment.status)
    )
    totals = {status: int(total or 0) for status, total in rows.all()}

    item = (
        await session.execute(select(EmergencyAidItem).where(EmergencyAidItem.id == item_id))
    ).scalar_one()
    item.quantity_received = totals.get("received", 0)
    item.quantity_committed = (
        totals.get("offered", 0) + totals.get("accepted", 0) + item.quantity_received
    )
    await session.flush()


# ---------------------------------------------------------------------------
# Commitments
# ---------------------------------------------------------------------------
async def offer(
    session: AsyncSession, item: EmergencyAidItem, *, user: User, quantity: int, note: str | None
) -> AidCommitment:
    """ "Kömək edə bilərəm" - I can help."""
    case = item.case
    if not case.accepts_offers:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            status_code=409,
            field="status",
            details={"reason": "case_not_active", "status": case.status},
        )

    existing = (
        await session.execute(
            select(AidCommitment).where(
                AidCommitment.item_id == item.id,
                AidCommitment.user_id == user.id,
                AidCommitment.status.in_(("offered", "accepted")),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            status_code=409,
            details={"reason": "already_offered", "commitment_id": existing.id},
        )

    commitment = AidCommitment(
        item_id=item.id,
        user_id=user.id,
        quantity=quantity,
        status="offered",
        note=(note or "").strip() or None,
    )
    session.add(commitment)
    await session.flush()
    await recount(session, item.id)

    # The offerer and the administrator now have a delivery to arrange.
    from app.services import messaging_service

    await messaging_service.system_thread(
        session,
        kind="emergency",
        context_id=case.id,
        user_ids=(case.created_by_admin_id, user.id),
    )

    await session.refresh(commitment, ["item", "user"])
    log.info("aid_offer", commitment_id=commitment.id, item_id=item.id, user_id=user.id)
    return commitment


async def set_commitment_status(
    session: AsyncSession, commitment: AidCommitment, *, status: str, by_admin: bool
) -> AidCommitment:
    """Move an offer along.

    `accepted` and `received` are the administrator's calls - they are
    statements about what the family has actually been given. `cancelled` is
    open to the offerer too: somebody whose circumstances change must be able
    to withdraw without asking permission.
    """
    allowed = COMMITMENT_TRANSITIONS.get(commitment.status, ())
    if status not in allowed:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            status_code=409,
            field="status",
            details={
                "reason": "invalid_transition",
                "from": commitment.status,
                "allowed": list(allowed),
            },
        )
    if status in ("accepted", "received") and not by_admin:
        raise AppError(ErrorCode.FORBIDDEN, status_code=403)

    now = datetime.now(UTC)
    if status == "accepted":
        commitment.accepted_at = now
    elif status == "received":
        commitment.received_at = now
    elif status == "cancelled":
        commitment.cancelled_at = now

    commitment.status = status
    await session.flush()
    await recount(session, commitment.item_id)

    if by_admin and status in ("accepted", "received"):
        await notification_service.notify(
            session,
            user_id=commitment.user_id,
            kind="aid_offer_accepted" if status == "accepted" else "aid_offer_received",
            link="/profile/aid",
            commitment_id=commitment.id,
        )

    await session.refresh(commitment, ["item", "user"])
    return commitment


async def commitments_of(session: AsyncSession, user_id: int) -> list[AidCommitment]:
    rows = await session.execute(
        select(AidCommitment)
        .where(AidCommitment.user_id == user_id)
        .options(selectinload(AidCommitment.item).selectinload(EmergencyAidItem.case))
        .order_by(AidCommitment.created_at.desc())
    )
    return list(rows.scalars())
