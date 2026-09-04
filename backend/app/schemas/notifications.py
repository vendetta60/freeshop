"""Notification DTOs (FreeShop_Prompt 12).

The `type` and its `payload` travel; the SENTENCE does not. A notification
stored as Azerbaijani text would still be Azerbaijani after the reader
switched to English, so the client owns one translated string per type and
interpolates the payload (plan.md 7.1).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.db.models import Notification


class NotificationOut(BaseModel):
    id: int
    type: str
    payload: dict[str, Any]
    link: str | None = None
    is_read: bool
    created_at: datetime

    @classmethod
    def of(cls, notification: Notification) -> NotificationOut:
        return cls(
            id=notification.id,
            type=notification.type,
            payload=notification.payload_json or {},
            link=notification.link,
            is_read=notification.read_at is not None,
            created_at=notification.created_at,
        )
