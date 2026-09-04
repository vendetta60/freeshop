"""Conversation and message DTOs (FreeShop_Prompt 3, 15).

A participant is rendered as a display name and nothing else - no phone, no
email, no address. Two people who are arranging a handover exchange whatever
they choose to type; the platform does not hand over a phone number because
somebody clicked a listing (FreeShop_Prompt 15).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import Conversation, Message, User

ConversationType = Literal["listing", "need", "loan", "emergency"]


class OpenConversationIn(BaseModel):
    """What a client may ask for: a subject, never a recipient.

    The other party is resolved server-side from the context object
    (messaging_service._counterpart). Accepting a `user_id` here would be an
    open channel to any account on the platform.
    """

    model_config = ConfigDict(extra="forbid")

    type: ConversationType
    context_id: int


class SendMessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: Annotated[str, Field(min_length=1, max_length=4000)]


class ParticipantOut(BaseModel):
    user_id: int
    display_name: str
    avatar_url: str | None = None

    @classmethod
    def of(cls, user: User) -> ParticipantOut:
        return cls(
            user_id=user.id,
            # `User.display_name`, which never falls back to a phone number or
            # an email address - see the property for why.
            display_name=user.display_name,
            avatar_url=user.avatar_url,
        )


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    body: str
    created_at: datetime
    edited_at: datetime | None = None
    is_deleted: bool = False

    @classmethod
    def of(cls, message: Message) -> MessageOut:
        deleted = message.deleted_at is not None
        return cls(
            id=message.id,
            conversation_id=message.conversation_id,
            sender_id=message.sender_id,
            # A deleted message keeps its place in the thread but not its
            # words, so the conversation still reads as a conversation.
            body="" if deleted else message.body,
            created_at=message.created_at,
            edited_at=message.edited_at,
            is_deleted=deleted,
        )


class ConversationOut(BaseModel):
    id: int
    type: ConversationType
    context_id: int | None = None
    # A short human label for the thing being discussed, resolved by the
    # router so the list does not need a second round trip to say what each
    # conversation is about.
    subject: str | None = None
    participants: list[ParticipantOut]
    unread_count: int = 0
    last_message_at: datetime | None = None
    last_message_preview: str | None = None
    created_at: datetime

    @classmethod
    def of(
        cls,
        conversation: Conversation,
        *,
        unread_count: int = 0,
        subject: str | None = None,
        preview: str | None = None,
    ) -> ConversationOut:
        return cls(
            id=conversation.id,
            type=conversation.type,
            context_id=conversation.context_id,
            subject=subject,
            participants=[ParticipantOut.of(p.user) for p in conversation.participants],
            unread_count=unread_count,
            last_message_at=conversation.last_message_at,
            last_message_preview=preview,
            created_at=conversation.created_at,
        )


class ConversationThreadOut(BaseModel):
    """One thread plus a page of its messages, newest first.

    `next_before_id` is the keyset cursor: pass it back as `before_id` to get
    the previous page. Null means the beginning of the conversation has been
    reached.
    """

    conversation: ConversationOut
    messages: list[MessageOut]
    next_before_id: int | None = None


class UnreadOut(BaseModel):
    """The navigation badge."""

    conversations: int
    notifications: int
