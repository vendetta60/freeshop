"""Messaging endpoints (FreeShop_Prompt 3, 15).

Every route here is behind `CurrentUser` AND behind
`messaging_service.require_participant`. The first says you are somebody; the
second says you are one of the two people in this thread. Neither is
sufficient alone, and the second is the one that matters.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, Lang
from app.core.errors import error_responses
from app.db.models import (
    Conversation,
    EmergencyAidCase,
    LoanRequest,
    Message,
    NeedRequest,
    Product,
)
from app.schemas.messaging import (
    ConversationOut,
    ConversationThreadOut,
    MessageOut,
    OpenConversationIn,
    SendMessageIn,
    UnreadOut,
)
from app.services import messaging_service, notification_service

router = APIRouter(
    prefix="/conversations",
    tags=["messages"],
    responses=error_responses(401, 403, 404, 409, 422),
)

NO_STORE = {"Cache-Control": "no-store"}

PREVIEW_CHARS = 90


async def _subjects(
    session: DbSession, conversations: list[Conversation], lang: str
) -> dict[int, str]:
    """A short label for what each thread is about.

    Batched by type so a twenty-thread inbox costs at most four queries
    rather than twenty (plan.md 11).
    """
    by_type: dict[str, list[int]] = {}
    for conversation in conversations:
        context_id = conversation.context_id
        if context_id is not None:
            by_type.setdefault(conversation.type, []).append(context_id)

    titles: dict[tuple[str, int], str] = {}

    if ids := by_type.get("listing"):
        for product in (
            await session.execute(select(Product).where(Product.id.in_(ids)))
        ).scalars():
            titles[("listing", product.id)] = product.title(lang)

    if ids := by_type.get("need"):
        for need in (
            await session.execute(select(NeedRequest).where(NeedRequest.id.in_(ids)))
        ).scalars():
            titles[("need", need.id)] = need.title

    if ids := by_type.get("loan"):
        for loan in (
            await session.execute(
                select(LoanRequest)
                .where(LoanRequest.id.in_(ids))
                .options(selectinload(LoanRequest.product))
            )
        ).scalars():
            titles[("loan", loan.id)] = loan.product.title(lang)

    if ids := by_type.get("emergency"):
        for case in (
            await session.execute(select(EmergencyAidCase).where(EmergencyAidCase.id.in_(ids)))
        ).scalars():
            titles[("emergency", case.id)] = case.title(lang)

    return {
        conversation.id: titles.get((conversation.type, conversation.context_id or 0), "")
        for conversation in conversations
    }


async def _previews(session: DbSession, conversation_ids: list[int]) -> dict[int, str]:
    """The last line of each thread.

    One query over the whole inbox, ordered newest-last so the dict keeps the
    most recent message per conversation. A per-thread LIMIT 1 would be the
    N+1 this avoids.
    """
    if not conversation_ids:
        return {}
    rows = await session.execute(
        select(Message.conversation_id, Message.body, Message.deleted_at)
        .where(Message.conversation_id.in_(conversation_ids))
        .order_by(Message.id.asc())
    )
    preview: dict[int, str] = {}
    for conversation_id, body, deleted_at in rows.all():
        preview[conversation_id] = "" if deleted_at else body[:PREVIEW_CHARS]
    return preview


@router.get("", summary="Your conversations, most recent first")
async def list_conversations(
    user: CurrentUser, session: DbSession, lang: Lang, response: Response
) -> list[ConversationOut]:
    response.headers.update(NO_STORE)
    conversations = await messaging_service.inbox(session, user.id)
    subjects = await _subjects(session, conversations, lang)
    previews = await _previews(session, [c.id for c in conversations])

    result: list[ConversationOut] = []
    for conversation in conversations:
        result.append(
            ConversationOut.of(
                conversation,
                unread_count=await messaging_service.unread_in(session, conversation.id, user.id),
                subject=subjects.get(conversation.id) or None,
                preview=previews.get(conversation.id) or None,
            )
        )
    return result


@router.get("/unread", summary="Badge counts for messages and notifications")
async def unread(user: CurrentUser, session: DbSession, response: Response) -> UnreadOut:
    """One call for both badges.

    Polling is the update mechanism (FreeShop_Prompt 3 permits it), so this
    is the most frequently hit authenticated endpoint in the application -
    which is exactly why it is two aggregates and not a list.
    """
    response.headers.update(NO_STORE)
    return UnreadOut(
        conversations=await messaging_service.total_unread(session, user.id),
        notifications=await notification_service.unread_count(session, user.id),
    )


@router.post("", status_code=status.HTTP_201_CREATED, summary="Open or reuse a conversation")
async def open_conversation(
    payload: OpenConversationIn,
    user: CurrentUser,
    session: DbSession,
    lang: Lang,
    response: Response,
) -> ConversationOut:
    """Get-or-create.

    The client names a SUBJECT - a listing, a need, a loan, a case - and the
    server works out who that reaches. A client that could name the recipient
    would be a channel to any account on the platform.
    """
    conversation, created = await messaging_service.open_thread(
        session, kind=payload.type, context_id=payload.context_id, user=user
    )
    await session.commit()
    if not created:
        response.status_code = status.HTTP_200_OK

    subjects = await _subjects(session, [conversation], lang)
    return ConversationOut.of(conversation, subject=subjects.get(conversation.id) or None)


@router.get("/{conversation_id}", summary="One thread and a page of its messages")
async def read_conversation(
    conversation_id: int,
    user: CurrentUser,
    session: DbSession,
    lang: Lang,
    response: Response,
    before_id: Annotated[int | None, Query(description="Keyset cursor")] = None,
    limit: Annotated[int, Query(ge=1, le=messaging_service.MAX_PAGE_SIZE)] = 30,
    mark_read: Annotated[bool, Query(description="Also clear the unread badge")] = True,
) -> ConversationThreadOut:
    response.headers.update(NO_STORE)
    conversation = await messaging_service.require_participant(session, conversation_id, user.id)

    messages = await messaging_service.page(
        session, conversation_id, before_id=before_id, limit=limit
    )

    # Reading only the FIRST page marks the thread read. Paging backwards
    # through history is not "I have seen the newest message", and treating
    # it as such would clear a badge the reader never looked at.
    if mark_read and before_id is None:
        await messaging_service.mark_read(session, conversation_id, user.id)
        await session.commit()

    subjects = await _subjects(session, [conversation], lang)
    return ConversationThreadOut(
        conversation=ConversationOut.of(
            conversation,
            unread_count=0
            if (mark_read and before_id is None)
            else await messaging_service.unread_in(session, conversation_id, user.id),
            subject=subjects.get(conversation.id) or None,
        ),
        messages=[MessageOut.of(message) for message in messages],
        # Full page means there may be more behind it.
        next_before_id=messages[-1].id if len(messages) == limit else None,
    )


@router.post(
    "/{conversation_id}/messages",
    status_code=status.HTTP_201_CREATED,
    summary="Send a message",
)
async def send_message(
    conversation_id: int, payload: SendMessageIn, user: CurrentUser, session: DbSession
) -> MessageOut:
    conversation = await messaging_service.require_participant(session, conversation_id, user.id)
    message = await messaging_service.send(
        session, conversation=conversation, sender=user, body=payload.body
    )
    await session.commit()
    return MessageOut.of(message)


@router.post("/{conversation_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_conversation_read(
    conversation_id: int, user: CurrentUser, session: DbSession
) -> None:
    await messaging_service.require_participant(session, conversation_id, user.id)
    await messaging_service.mark_read(session, conversation_id, user.id)
    await session.commit()
