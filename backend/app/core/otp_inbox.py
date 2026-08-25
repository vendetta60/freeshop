"""In-memory OTP inbox backing the dev-only viewer (plan.md 9.11).

Conceptually Mailpit, but for one-time codes: the console channel appends
here as well as writing a boxed line to stdout, so the whole phone-verify
flow can be demonstrated on one screen with no SMS gateway.

Safety properties, by construction:
  * memory only - never a table, never a file
  * phone numbers are stored masked
  * entries expire and the buffer is bounded
  * the router exposing this is not registered outside development
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.logging import mask_phone

MAX_ENTRIES = 20


@dataclass(frozen=True, slots=True)
class OtpEntry:
    phone_masked: str
    code: str
    purpose: str
    channel: str
    created_at: datetime
    expires_at: datetime

    @property
    def is_expired(self) -> bool:
        return datetime.now(UTC) >= self.expires_at

    def as_dict(self) -> dict[str, str | int | bool]:
        remaining = int((self.expires_at - datetime.now(UTC)).total_seconds())
        return {
            "phone": self.phone_masked,
            "code": self.code,
            "purpose": self.purpose,
            "channel": self.channel,
            "created_at": self.created_at.isoformat(),
            "expires_in": max(0, remaining),
            "expired": self.is_expired,
        }


_buffer: deque[OtpEntry] = deque(maxlen=MAX_ENTRIES)


def record(
    *,
    phone: str,
    code: str,
    purpose: str,
    channel: str,
    expires_at: datetime,
) -> None:
    """Append an entry. Called by the console OTP channel (phase 4)."""
    _buffer.appendleft(
        OtpEntry(
            phone_masked=mask_phone(phone),
            code=code,
            purpose=purpose,
            channel=channel,
            created_at=datetime.now(UTC),
            expires_at=expires_at,
        )
    )


def recent() -> list[dict[str, str | int | bool]]:
    """Newest first. Expired entries are dropped as they are read."""
    live = [e for e in _buffer if not e.is_expired]
    return [e.as_dict() for e in live]


def clear() -> None:
    _buffer.clear()
