"""Structured JSON logging to stdout.

Never log tokens, OTP codes, full phone numbers, or emails at INFO level
(plan.md 10). ``mask_phone`` exists so that rule is easy to follow.
"""

from __future__ import annotations

import contextlib
import logging
import sys
from typing import Any

import structlog

from app.config import get_settings


def mask_phone(phone: str | None) -> str:
    """+994501234567 -> +99450***4567 . Safe to log."""
    if not phone:
        return "<none>"
    if len(phone) <= 8:
        return phone[:3] + "***"
    return f"{phone[:6]}***{phone[-4:]}"


def mask_email(email: str | None) -> str:
    """aysel@example.com -> a***@example.com . Safe to log."""
    if not email or "@" not in email:
        return "<none>"
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"


def _force_utf8_stdio() -> None:
    """Make stdout/stderr UTF-8, whatever the console code page is.

    On a Windows terminal the default is cp1252, so printing Azerbaijani text
    or the boxed OTP line raises UnicodeEncodeError - which surfaced as a 500
    on /auth/phone/send-otp rather than as a logging problem. errors=replace
    so a stray character can never take down a request again.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            # A stream that cannot be reconfigured (a pipe under some
            # runners) is not worth failing startup over.
            with contextlib.suppress(ValueError, OSError):
                reconfigure(encoding="utf-8", errors="replace")


def configure_logging() -> None:
    settings = get_settings()
    _force_utf8_stdio()

    shared: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Human-readable in dev, JSON lines in production (plan.md 12.3).
    renderer: Any = (
        structlog.dev.ConsoleRenderer(colors=True)
        if settings.is_development
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[*shared, renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)

    # Third-party DEBUG output is worse than useless here: aiosqlite logs every
    # cursor operation, which would bury the boxed OTP line the demo relies on
    # (plan.md 9.11). Silence the noisy ones explicitly rather than globally
    # raising the level, so our own DEBUG stays available when needed.
    for noisy in ("aiosqlite", "sqlalchemy.engine", "multipart", "asyncio", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # uvicorn's access log duplicates what we emit; keep it quiet.
    logging.getLogger("uvicorn.access").handlers.clear()


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
