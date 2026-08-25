"""Development-only endpoints.

SECURITY (plan.md 9.11, 10): this router is *never registered* when
ENV != development. The guard lives in the application factory, not in an
``if`` inside a handler - there is therefore no code path that can serve
these routes in production, and ``tests/test_dev_router.py`` asserts a 404
when the app is built with ENV=production.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core import otp_inbox

router = APIRouter(prefix="/dev", tags=["dev"])


@router.get("/otp-inbox", summary="Recent OTP codes (development only)")
async def read_otp_inbox() -> dict[str, Any]:
    """Return the last few OTP codes issued by the console channel.

    Phone numbers are masked; codes disappear when they expire.
    """
    return {"items": otp_inbox.recent()}


@router.delete("/otp-inbox", status_code=204, summary="Clear the OTP inbox")
async def clear_otp_inbox() -> None:
    otp_inbox.clear()
