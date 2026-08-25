"""OTP delivery channels (plan.md D3, 9.11).

Delivery is behind an interface so the demo runs on `console` with no gateway,
and switching to a real provider is an env var rather than a code change.
That is the whole argument for the adapter: it is the part of the design that
survives not having an SMS budget.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class OtpChannel(ABC):
    """Delivers a one-time code to a phone number."""

    name: str

    @abstractmethod
    async def send(self, *, phone: str, code: str, purpose: str, expires_at: datetime) -> None:
        """Deliver the code. Raising means delivery failed and the caller
        should surface an error rather than pretend a code was sent."""

    @property
    def usable_in_production(self) -> bool:
        """False for channels that expose codes locally (plan.md 9.11)."""
        return True
