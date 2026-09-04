"""In-app notifications (FreeShop_Prompt 12)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.core.errors import error_responses
from app.schemas.notifications import NotificationOut
from app.services import notification_service

router = APIRouter(
    prefix="/notifications", tags=["notifications"], responses=error_responses(401, 404, 422)
)

NO_STORE = {"Cache-Control": "no-store"}


@router.get("", summary="Your notifications, newest first")
async def list_notifications(
    user: CurrentUser,
    session: DbSession,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=notification_service.FEED_LIMIT)] = 30,
) -> list[NotificationOut]:
    response.headers.update(NO_STORE)
    rows = await notification_service.feed(session, user.id, limit=limit)
    return [NotificationOut.of(row) for row in rows]


@router.post("/read", status_code=status.HTTP_204_NO_CONTENT, summary="Mark all read")
async def mark_all_read(user: CurrentUser, session: DbSession) -> None:
    await notification_service.mark_read(session, user.id)
    await session.commit()


@router.post(
    "/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark one read",
)
async def mark_one_read(notification_id: int, user: CurrentUser, session: DbSession) -> None:
    """Scoped by user as well as by id.

    A 204 either way: whether the id belonged to somebody else or never
    existed, the honest answer to "clear this" is that nothing of yours is
    now unread under that id.
    """
    await notification_service.mark_read(session, user.id, notification_id=notification_id)
    await session.commit()
