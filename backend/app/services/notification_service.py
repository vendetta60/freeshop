"""In-app notifications (FreeShop_Prompt 12).

One `notify()` for every producer. The rule that matters is at the bottom of
this docstring and is enforced by the signature: a notification is a side
effect of something that already happened, so it never raises. A failure to
record "your loan was approved" must not roll back the approval.

Producers call this INSIDE the caller's transaction and do not commit; the
endpoint that owns the request commits once, so a notification cannot outlive
the event it describes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Notification

log = get_logger(__name__)

# A person who is not signed in cannot read these, and a person notified about
# their own action learns nothing. Both are caught here rather than at each of
# the dozen call sites.
FEED_LIMIT = 50


async def notify(
    session: AsyncSession,
    *,
    user_id: int | None,
    # `kind`, not `type`: the column is `type` but shadowing the builtin in a
    # function signature is banned by the lint config (ruff A002).
    kind: str,
    link: str | None = None,
    actor_id: int | None = None,
    **payload: Any,
) -> Notification | None:
    """Record one event for one person.

    Returns None when there is nobody to tell, or when the only person to
    tell is the one who caused it - telling somebody about their own click is
    noise, and noise is what makes a notification list get switched off.
    """
    if user_id is None:
        return None
    if actor_id is not None and actor_id == user_id:
        return None

    notification = Notification(
        user_id=user_id,
        type=kind,
        payload_json=payload,
        link=link,
    )
    session.add(notification)
    return notification


async def unread_count(session: AsyncSession, user_id: int) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        )
    ).scalar_one()


async def feed(
    session: AsyncSession, user_id: int, *, limit: int = FEED_LIMIT
) -> list[Notification]:
    rows = await session.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(min(limit, FEED_LIMIT))
    )
    return list(rows.scalars())


async def mark_read(
    session: AsyncSession, user_id: int, *, notification_id: int | None = None
) -> int:
    """Mark one notification read, or all of them. Returns the number changed.

    Scoped by `user_id` as well as by id, never by id alone: an endpoint that
    trusts the id would let anyone clear anyone else's badge (plan.md 10, IDOR).
    """
    stmt = (
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    if notification_id is not None:
        stmt = stmt.where(Notification.id == notification_id)
    # `execute` is typed as returning Result; an UPDATE actually returns a
    # CursorResult, which is the one that carries rowcount.
    result = cast("CursorResult[Any]", await session.execute(stmt))
    return result.rowcount or 0
