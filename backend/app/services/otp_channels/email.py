"""Email channel - free via SMTP (plan.md 18/W1).

Free with a Gmail app password, but of limited use for someone registering
*by phone*: it can only reach a user who already has an email on file. Kept
as a fallback rather than a default for that reason.
"""

from __future__ import annotations

import smtplib
from datetime import datetime
from email.message import EmailMessage

from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.core.logging import get_logger, mask_email
from app.services.otp_channels.base import OtpChannel

log = get_logger(__name__)


class EmailOtpChannel(OtpChannel):
    name = "email"

    async def send(self, *, phone: str, code: str, purpose: str, expires_at: datetime) -> None:
        settings = get_settings()
        if not (settings.smtp_host and settings.smtp_user and settings.smtp_from):
            raise RuntimeError("SMTP_HOST, SMTP_USER and SMTP_FROM must be set")

        # The caller resolves the address; this channel is only reachable for
        # users who have one (see otp_service).
        recipient = getattr(self, "recipient", None)
        if not recipient:
            raise RuntimeError("email channel requires a recipient address")

        minutes = max(1, settings.otp_ttl_seconds // 60)
        message = EmailMessage()
        message["Subject"] = f"{settings.app_name} — təsdiq kodu"
        message["From"] = settings.smtp_from
        message["To"] = recipient
        message.set_content(
            f"Təsdiq kodunuz: {code}\n\n"
            f"Kod {minutes} dəqiqə ərzində etibarlıdır.\n"
            f"Bu sorğunu siz göndərməmisinizsə, məktubu nəzərə almayın."
        )

        # smtplib is blocking; sending inline would stall the event loop for
        # the whole round trip to the mail server.
        await run_in_threadpool(self._deliver, message)
        log.info("otp_email_sent", to=mask_email(recipient), purpose=purpose)

    @staticmethod
    def _deliver(message: EmailMessage) -> None:
        settings = get_settings()
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
