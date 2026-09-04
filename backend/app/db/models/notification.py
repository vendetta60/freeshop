"""In-app notifications (FreeShop_Prompt 12).

The project has no notification abstraction to extend, and no push or SMS
transport that is free at this scale (plan.md D3 already ruled Twilio out), so
this is the in-app one: a row per event, read over the same API as everything
else.

WHY THE PAYLOAD IS JSON AND THE TEXT IS NOT STORED:
notifications outlive the language the reader had selected when they arrived.
Storing "Sizə mesaj var" would freeze a row into Azerbaijani; storing
`{"conversation_id": 12}` under a stable `type` lets the client translate at
render time, which is where every other string in this application is
translated (plan.md 7.1). It is also what makes adding a transport later - a
digest email, a Telegram bot - a new consumer of these rows rather than a
rewrite of them.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UtcDateTime

if TYPE_CHECKING:
    from app.db.models.user import User

# Stable keys. The frontend owns one translated string per member, so adding
# one here without adding the string shows the key - loud, not silent.
NOTIFICATION_TYPES = (
    "message_received",
    "request_accepted",
    "request_not_selected",
    "need_match_found",
    "listing_match_found",
    "loan_requested",
    "loan_approved",
    "loan_due_soon",
    "loan_returned",
    "need_approved",
    "need_rejected",
    "aid_offer_accepted",
    "aid_offer_received",
)


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    # Where clicking it should go, as an app-relative path. Computed once by
    # the producer, so the client does not need a switch over `type` to
    # navigate - only to render.
    link: Mapped[str | None] = mapped_column(String(200))

    read_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    user: Mapped[User] = relationship(back_populates="notifications")

    __table_args__ = (
        # The two queries this table serves: the unread badge, and the list.
        Index("ix_notifications_unread", "user_id", "read_at"),
        Index("ix_notifications_feed", "user_id", "created_at"),
    )
