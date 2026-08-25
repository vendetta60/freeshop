"""Console channel - the decided demo path (plan.md 18/W1)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.core import otp_inbox
from app.core.logging import get_logger, mask_phone
from app.services.otp_channels.base import OtpChannel

log = get_logger(__name__)


class ConsoleOtpChannel(OtpChannel):
    """Prints the code and records it in the dev inbox.

    Deliberately watchable rather than a bare print buried in uvicorn output:
    a boxed line is findable instantly in a scrolling terminal on a projector,
    and /dev/otp-inbox shows the same codes in the browser so the whole verify
    flow demos on one screen with no SMS gateway.
    """

    name = "console"

    @property
    def usable_in_production(self) -> bool:
        # Printing live codes to the log is a demo affordance, never a
        # production one. Startup refuses this combination (app/config.py).
        return False

    async def send(self, *, phone: str, code: str, purpose: str, expires_at: datetime) -> None:
        remaining = int((expires_at - datetime.now(UTC)).total_seconds())
        minutes, seconds = divmod(max(0, remaining), 60)

        banner = (
            f"\n╔══════════════ OTP ══════════════╗"
            f"\n║ phone   {mask_phone(phone):<24}║"
            f"\n║ code    {code:<24}║"
            f"\n║ purpose {purpose:<24}║"
            f"\n║ expires {f'{minutes:02d}:{seconds:02d}':<24}║"
            f"\n╚═════════════════════════════════╝\n"
        )
        log.info("otp_console", phone=mask_phone(phone), purpose=purpose)
        # structlog escapes newlines, so the box is printed separately.
        # Guarded: a console that cannot render these glyphs must not turn a
        # working OTP into a 500 (see _force_utf8_stdio in core/logging.py).
        try:
            print(banner, flush=True)  # noqa: T201 - the point of this channel
        except UnicodeEncodeError:
            print(f"[OTP] {mask_phone(phone)} code={code} purpose={purpose}", flush=True)  # noqa: T201

        otp_inbox.record(
            phone=phone,
            code=code,
            purpose=purpose,
            channel=self.name,
            expires_at=expires_at,
        )
