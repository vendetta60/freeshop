"""Conversations and messages (FreeShop_Prompt 3, 15).

THE AUTHORISATION RULE, IN ONE SENTENCE: you may read a conversation if and
only if a `ConversationParticipant` row names you.

Everything else here exists to make that sentence true. Participants are
written by `open_thread` from the context object - the listing's owner, the
need's poster, the loan's two parties, the case's administrator - and there
is no endpoint that adds a participant. That is deliberate: an API that lets
a client name the other party is an API where a stranger can insert
themselves into a conversation about somebody's house burning down.

Reads go through `require_participant`, which returns 404 rather than 403 for
a thread you are not in. Distinguishing "does not exist" from "not yours"
would confirm that two named people are talking.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError, ErrorCode, NotFoundError
from app.core.logging import get_logger
from app.db.models import (
    Conversation,
    ConversationParticipant,
    EmergencyAidCase,
    LoanRequest,
    Message,
    NeedRequest,
    Product,
    User,
)

log = get_logger(__name__)

MAX_BODY_CHARS = 4000
PAGE_SIZE = 30
MAX_PAGE_SIZE = 100

# Every conversation this module returns is serialised by `ConversationOut`,
# which reads each participant's display name. Loading the participants
# WITHOUT their users leaves that a lazy load, and a lazy load in async
# SQLAlchemy is not a slow query - it is a MissingGreenlet exception at
# render time. One constant, so no loader can be written that forgets.
CONVERSATION_RELATIONS = (
    selectinload(Conversation.participants).selectinload(ConversationParticipant.user),
)


# ---------------------------------------------------------------------------
# Authorisation
# ---------------------------------------------------------------------------
async def require_participant(
    session: AsyncSession, conversation_id: int, user_id: int
) -> Conversation:
    """The gate. Every read and every write goes through it."""
    conversation = (
        await session.execute(
            select(Conversation)
            .join(ConversationParticipant)
            .where(
                Conversation.id == conversation_id,
                ConversationParticipant.user_id == user_id,
            )
            .options(*CONVERSATION_RELATIONS)
        )
    ).scalar_one_or_none()

    # 404, not 403 - see the module docstring.
    if conversation is None:
        raise NotFoundError()
    return conversation


async def _reload(session: AsyncSession, conversation_id: int) -> Conversation:
    """Re-read a freshly written conversation with its participants AND their
    users loaded.

    `session.refresh(conversation, ["participants"])` reloads the collection
    but leaves each row's `user` lazy, which is a MissingGreenlet the moment
    the serializer asks for a display name.
    """
    return (
        await session.execute(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(*CONVERSATION_RELATIONS)
        )
    ).scalar_one()


async def _participant_row(
    session: AsyncSession, conversation_id: int, user_id: int
) -> ConversationParticipant:
    row = (
        await session.execute(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError()
    return row


# ---------------------------------------------------------------------------
# Opening a thread
# ---------------------------------------------------------------------------
async def _counterpart(
    session: AsyncSession, *, kind: str, context_id: int, user: User
) -> tuple[int, int]:
    """(other_user_id, context_id) for a thread the caller may open.

    This function decides who a person is allowed to write to, so every
    branch resolves the other party from the DATABASE, never from the
    request. A caller supplies what they want to talk about; they never
    supply whom they reach.
    """
    if kind == "listing":
        product = (
            await session.execute(select(Product).where(Product.id == context_id, Product.public()))
        ).scalar_one_or_none()
        if product is None:
            raise NotFoundError()
        if product.owner_id == user.id:
            # Messaging yourself about your own listing is not a feature.
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                status_code=409,
                details={"reason": "own_listing"},
            )
        return product.owner_id, product.id

    if kind == "need":
        need = (
            await session.execute(
                select(NeedRequest).where(NeedRequest.id == context_id, NeedRequest.public())
            )
        ).scalar_one_or_none()
        if need is None:
            raise NotFoundError()
        if need.user_id == user.id:
            raise AppError(
                ErrorCode.VALIDATION_ERROR, status_code=409, details={"reason": "own_need"}
            )
        return need.user_id, need.id

    if kind == "loan":
        loan = (
            await session.execute(
                select(LoanRequest)
                .where(LoanRequest.id == context_id)
                .options(selectinload(LoanRequest.product))
            )
        ).scalar_one_or_none()
        if loan is None:
            raise NotFoundError()
        # Only the two parties to the loan, and each reaches the other.
        if user.id == loan.borrower_id:
            return loan.product.owner_id, loan.id
        if user.id == loan.product.owner_id:
            return loan.borrower_id, loan.id
        raise NotFoundError()

    if kind == "emergency":
        case = (
            await session.execute(select(EmergencyAidCase).where(EmergencyAidCase.id == context_id))
        ).scalar_one_or_none()
        if case is None or not case.is_public:
            raise NotFoundError()
        # An aid thread reaches the administrator who published the case, not
        # the family. Rule F: the beneficiary is not a contactable party.
        if case.created_by_admin_id == user.id:
            raise AppError(
                ErrorCode.VALIDATION_ERROR, status_code=409, details={"reason": "own_case"}
            )
        return case.created_by_admin_id, case.id

    raise AppError(ErrorCode.VALIDATION_ERROR, status_code=422, field="type")


async def open_thread(
    session: AsyncSession, *, kind: str, context_id: int, user: User
) -> tuple[Conversation, bool]:
    """Get-or-create the thread between the caller and the other party.

    Returns (conversation, created). Get-OR-CREATE rather than create: two
    people discussing one ladder have one thread, and a "Message" button that
    starts a new empty conversation on every click is how an inbox becomes
    unusable.
    """
    other_id, resolved_id = await _counterpart(session, kind=kind, context_id=context_id, user=user)

    column = {
        "listing": Conversation.listing_id,
        "need": Conversation.need_id,
        "loan": Conversation.loan_id,
        "emergency": Conversation.emergency_case_id,
    }[kind]

    # An existing thread on this context that BOTH of them are in. The two
    # EXISTS clauses are what stops a third party's thread about the same
    # listing being handed over.
    existing = (
        await session.execute(
            select(Conversation)
            .where(
                Conversation.type == kind,
                column == resolved_id,
                Conversation.participants.any(ConversationParticipant.user_id == user.id),
                Conversation.participants.any(ConversationParticipant.user_id == other_id),
            )
            .options(*CONVERSATION_RELATIONS)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False

    conversation = Conversation(type=kind)
    setattr(conversation, column.key, resolved_id)
    session.add(conversation)
    await session.flush()

    session.add_all(
        [
            ConversationParticipant(conversation_id=conversation.id, user_id=user.id),
            ConversationParticipant(conversation_id=conversation.id, user_id=other_id),
        ]
    )
    await session.flush()
    conversation = await _reload(session, conversation.id)
    log.info(
        "conversation_opened",
        conversation_id=conversation.id,
        type=kind,
        context_id=resolved_id,
    )
    return conversation, True


async def system_thread(
    session: AsyncSession, *, kind: str, context_id: int, user_ids: tuple[int, int]
) -> Conversation:
    """Open a thread the SERVER decided on, between two known people.

    Used when an event rather than a click creates the need to talk - a loan
    being approved, for instance. It bypasses `_counterpart` because the
    parties are already known to the caller from the row it just wrote; it
    does NOT bypass the participant rows, which are still the only key to
    the thread.
    """
    first, second = user_ids
    if first == second:
        raise AppError(ErrorCode.VALIDATION_ERROR, status_code=409)

    column = {
        "listing": Conversation.listing_id,
        "need": Conversation.need_id,
        "loan": Conversation.loan_id,
        "emergency": Conversation.emergency_case_id,
    }[kind]

    existing = (
        await session.execute(
            select(Conversation)
            .where(
                Conversation.type == kind,
                column == context_id,
                Conversation.participants.any(ConversationParticipant.user_id == first),
                Conversation.participants.any(ConversationParticipant.user_id == second),
            )
            .options(*CONVERSATION_RELATIONS)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    conversation = Conversation(type=kind)
    setattr(conversation, column.key, context_id)
    session.add(conversation)
    await session.flush()
    session.add_all(
        [
            ConversationParticipant(conversation_id=conversation.id, user_id=first),
            ConversationParticipant(conversation_id=conversation.id, user_id=second),
        ]
    )
    await session.flush()
    return await _reload(session, conversation.id)


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------
async def send(
    session: AsyncSession, *, conversation: Conversation, sender: User, body: str
) -> Message:
    from app.services import notification_service

    text = body.strip()
    if not text:
        raise AppError(ErrorCode.VALIDATION_ERROR, status_code=422, field="body")
    if len(text) > MAX_BODY_CHARS:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            status_code=422,
            field="body",
            details={"reason": "too_long", "limit": MAX_BODY_CHARS},
        )

    message = Message(conversation_id=conversation.id, sender_id=sender.id, body=text)
    session.add(message)

    now = datetime.now(UTC)
    conversation.last_message_at = now

    # Sending is also reading: leaving your own message unread would show the
    # sender a badge for something they just typed.
    mine = await _participant_row(session, conversation.id, sender.id)
    mine.last_read_at = now

    for participant in conversation.participants:
        await notification_service.notify(
            session,
            user_id=participant.user_id,
            actor_id=sender.id,
            kind="message_received",
            link=f"/messages/{conversation.id}",
            conversation_id=conversation.id,
        )

    await session.flush()
    await session.refresh(message, ["sender"])
    return message


async def page(
    session: AsyncSession,
    conversation_id: int,
    *,
    before_id: int | None = None,
    limit: int = PAGE_SIZE,
) -> list[Message]:
    """One page of a thread, newest first.

    Keyset pagination on the id rather than OFFSET: a long conversation is
    read while it is being written to, and an offset shifts under the reader
    every time the other person types, which duplicates or skips a message.
    """
    stmt = select(Message).where(Message.conversation_id == conversation_id)
    if before_id is not None:
        stmt = stmt.where(Message.id < before_id)
    stmt = (
        stmt.options(selectinload(Message.sender))
        .order_by(Message.id.desc())
        .limit(min(limit, MAX_PAGE_SIZE))
    )
    return list((await session.execute(stmt)).scalars())


async def mark_read(session: AsyncSession, conversation_id: int, user_id: int) -> None:
    row = await _participant_row(session, conversation_id, user_id)
    row.last_read_at = datetime.now(UTC)
    await session.flush()


async def unread_in(session: AsyncSession, conversation_id: int, user_id: int) -> int:
    row = await _participant_row(session, conversation_id, user_id)
    stmt = (
        select(func.count())
        .select_from(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.sender_id != user_id,
            Message.deleted_at.is_(None),
        )
    )
    if row.last_read_at is not None:
        stmt = stmt.where(Message.created_at > row.last_read_at)
    return (await session.execute(stmt)).scalar_one()


async def inbox(session: AsyncSession, user_id: int, *, limit: int = 50) -> list[Conversation]:
    """Threads this person is in, most recently active first."""
    rows = await session.execute(
        select(Conversation)
        .join(ConversationParticipant)
        .where(ConversationParticipant.user_id == user_id)
        .options(selectinload(Conversation.participants).selectinload(ConversationParticipant.user))
        .order_by(
            # A thread with no messages yet still has to sort somewhere, and
            # its creation time is the honest answer.
            func.coalesce(Conversation.last_message_at, Conversation.created_at).desc(),
            Conversation.id.desc(),
        )
        .limit(limit)
    )
    return list(rows.scalars())


async def total_unread(session: AsyncSession, user_id: int) -> int:
    """The one number the navigation badge needs.

    A single aggregate rather than a loop over threads: the badge is rendered
    on every page, and N+1 in a header is N+1 everywhere.
    """
    result = await session.execute(
        select(func.count(Message.id))
        .select_from(Message)
        .join(
            ConversationParticipant,
            ConversationParticipant.conversation_id == Message.conversation_id,
        )
        .where(
            ConversationParticipant.user_id == user_id,
            Message.sender_id != user_id,
            Message.deleted_at.is_(None),
            or_(
                ConversationParticipant.last_read_at.is_(None),
                Message.created_at > ConversationParticipant.last_read_at,
            ),
        )
    )
    return result.scalar_one()
