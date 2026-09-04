"""Conversations between the two people involved in one item
(FreeShop_Prompt 3).

Threads, not a flat inbox: every message belongs to a conversation, and every
conversation is anchored to the thing being discussed. The anchor is what
makes authorisation decidable - a participant row exists because the server
put it there when the conversation was opened, so "may this person read this
thread?" is a lookup rather than a judgement call.

No WebSockets. The deployment is one uvicorn process behind Caddy
(plan.md 12.3) and the client polls; a socket layer would add a connection
lifecycle, a reconnect story and a second auth path for a board where
messages arrive minutes apart.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UtcDateTime

if TYPE_CHECKING:
    from app.db.models.user import User

# What the thread is about. The type is not decoration: it decides which
# context id must be present, and which authorisation rule opens the thread.
CONVERSATION_TYPES = ("listing", "need", "loan", "emergency")


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(12), nullable=False)

    # Exactly one of these is set, matching `type`. Nullable FKs rather than
    # a polymorphic (type, id) pair so the database still enforces that the
    # thing being discussed exists.
    listing_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    need_id: Mapped[int | None] = mapped_column(ForeignKey("need_requests.id", ondelete="CASCADE"))
    loan_id: Mapped[int | None] = mapped_column(ForeignKey("loan_requests.id", ondelete="CASCADE"))
    emergency_case_id: Mapped[int | None] = mapped_column(
        ForeignKey("emergency_aid_cases.id", ondelete="CASCADE")
    )

    # Denormalised so the conversation list can sort without touching the
    # messages table. A list endpoint that reads every thread's last message
    # to order itself is the N+1 this column exists to prevent.
    last_message_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    participants: Mapped[list[ConversationParticipant]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "type IN ('listing','need','loan','emergency')", name="conversation_type_valid"
        ),
        Index("ix_conversations_listing", "listing_id"),
        Index("ix_conversations_need", "need_id"),
        Index("ix_conversations_loan", "loan_id"),
        Index("ix_conversations_emergency", "emergency_case_id"),
        Index("ix_conversations_recent", "last_message_at"),
    )

    @property
    def context_id(self) -> int | None:
        return {
            "listing": self.listing_id,
            "need": self.need_id,
            "loan": self.loan_id,
            "emergency": self.emergency_case_id,
        }.get(self.type)


class ConversationParticipant(Base, TimestampMixin):
    """Membership. The presence of this row IS the authorisation."""

    __tablename__ = "conversation_participants"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # Unread count = messages after this instant that this person did not
    # send. A timestamp rather than a counter, so marking read is idempotent
    # and cannot drift out of step with the messages themselves.
    last_read_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    conversation: Mapped[Conversation] = relationship(back_populates="participants")
    user: Mapped[User] = relationship(back_populates="conversation_memberships")

    __table_args__ = (
        UniqueConstraint("conversation_id", "user_id", name="uq_participant_once"),
        Index("ix_participants_user", "user_id", "conversation_id"),
    )


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    body: Mapped[str] = mapped_column(Text, nullable=False)
    edited_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    # Soft delete, matching the project's existing history rule (plan.md D7):
    # the row stays so the thread keeps its shape, the body stops being served.
    deleted_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    sender: Mapped[User] = relationship()

    __table_args__ = (
        # The pagination index: newest-first within one thread, which is the
        # only order this table is ever read in.
        Index("ix_messages_thread", "conversation_id", "id"),
        Index("ix_messages_unread", "conversation_id", "created_at"),
    )
