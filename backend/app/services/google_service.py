"""Google ID-token verification (plan.md 6.3).

Verification happens server-side. A client-supplied email is a claim, not
evidence; only Google's signature over the ID token makes it a fact.
"""

from __future__ import annotations

from typing import Any

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger

log = get_logger(__name__)

ISSUERS = ("accounts.google.com", "https://accounts.google.com")


class GoogleProfile:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.google_id: str = str(payload["sub"])
        self.email: str = str(payload.get("email", "")).lower()
        self.email_verified: bool = bool(payload.get("email_verified", False))
        self.full_name: str | None = payload.get("name")
        self.picture: str | None = payload.get("picture")


def _verify_blocking(credential: str, client_id: str) -> dict[str, Any]:
    # google-auth performs a blocking HTTPS fetch of Google's signing keys.
    # The library ships no type stubs, hence the explicit ignore rather than
    # loosening mypy for the whole module.
    payload: dict[str, Any] = google_id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
        credential, google_requests.Request(), client_id
    )
    return payload


async def verify_credential(credential: str) -> GoogleProfile:
    settings = get_settings()

    if not settings.google_configured:
        # Expected until credentials exist (plan.md 18/W2). A clear code beats
        # a stack trace from a library called with an empty audience.
        raise AppError(ErrorCode.GOOGLE_NOT_CONFIGURED, status_code=503)

    try:
        payload = await run_in_threadpool(_verify_blocking, credential, settings.google_client_id)
    except ValueError as exc:
        log.info("google_token_rejected", reason=str(exc)[:120])
        raise AppError(ErrorCode.GOOGLE_TOKEN_INVALID, status_code=401) from exc

    if payload.get("iss") not in ISSUERS:
        raise AppError(ErrorCode.GOOGLE_TOKEN_INVALID, status_code=401)

    profile = GoogleProfile(payload)

    # An unverified address could belong to anyone; accepting it would let a
    # signup with someone else's email take over their account.
    if not profile.email or not profile.email_verified:
        raise AppError(
            ErrorCode.GOOGLE_TOKEN_INVALID,
            status_code=401,
            details={"reason": "email_not_verified"},
        )

    return profile
