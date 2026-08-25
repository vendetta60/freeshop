"""Channel registry."""

from __future__ import annotations

from app.config import get_settings
from app.services.otp_channels.base import OtpChannel
from app.services.otp_channels.console import ConsoleOtpChannel
from app.services.otp_channels.email import EmailOtpChannel
from app.services.otp_channels.telegram import TelegramOtpChannel

__all__ = [
    "ConsoleOtpChannel",
    "EmailOtpChannel",
    "OtpChannel",
    "TelegramOtpChannel",
    "get_channel",
]

_CHANNELS: dict[str, type[OtpChannel]] = {
    "console": ConsoleOtpChannel,
    "telegram": TelegramOtpChannel,
    "email": EmailOtpChannel,
    # 'sms' is deliberately absent: no free gateway serves +994, so there is
    # nothing honest to register. Add a provider class here when one is paid for.
}


def get_channel() -> OtpChannel:
    settings = get_settings()
    channel_class = _CHANNELS.get(settings.otp_channel)
    if channel_class is None:
        raise RuntimeError(
            f"OTP_CHANNEL={settings.otp_channel!r} has no implementation. "
            f"Available: {', '.join(sorted(_CHANNELS))}"
        )
    return channel_class()
