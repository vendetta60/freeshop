"""Telegram bot channel - the free production option (plan.md 18/W1).

Free and unlimited, but the recipient must have pressed Start on the bot so
it knows their chat id. That handshake is why this is not the default: a
channel that silently fails for first-time users is worse than one that is
honestly switched off.
"""

from __future__ import annotations

from datetime import datetime

import httpx

from app.config import get_settings
from app.core.logging import get_logger
from app.services.otp_channels.base import OtpChannel

log = get_logger(__name__)


class TelegramOtpChannel(OtpChannel):
    name = "telegram"

    async def send(self, *, phone: str, code: str, purpose: str, expires_at: datetime) -> None:
        settings = get_settings()
        if not settings.telegram_bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

        # Chat-id resolution belongs to a `telegram_chat_id` column on users,
        # populated when they link the bot. Until that exists this channel
        # cannot address anyone, so fail loudly rather than appear to work.
        raise NotImplementedError(
            "Telegram delivery needs users.telegram_chat_id, populated by the bot "
            "link flow. Wire it at plan.md 18/W1 before enabling this channel."
        )

    async def _post(self, chat_id: str, text: str) -> None:
        settings = get_settings()
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json={"chat_id": chat_id, "text": text})
            if response.status_code >= 400:
                log.warning("telegram_send_failed", status=response.status_code)
                response.raise_for_status()
