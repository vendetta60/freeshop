"""Request rate limits and the body-size cap (plan.md 10).

WHY NOT slowapi, which the dependency list carries:
its limiter raises its own exception with its own JSON body, so every 429 in
the application would have a different shape from every other error - and the
uniform envelope (plan.md 6.1) is the thing the frontend's error handling is
built on. Wiring a custom handler to translate it back is more code than the
sliding window below, which is about thirty lines.

The counters are in-process. That is correct for this deployment - one
uvicorn process behind Caddy on a single host (plan.md 12.3) - and it is the
part to replace with Redis if the app is ever run with more than one worker.
That limitation is stated here rather than discovered later.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.core.errors import ErrorCode
from app.core.i18n import translate_error
from app.core.logging import get_logger

log = get_logger(__name__)

# (path prefix, requests, window seconds). The first match wins, so the
# specific buckets are listed before the global one.
RULES: tuple[tuple[str, int, int], ...] = (
    # The credential-taking endpoints get the tightest bucket - they are what
    # is worth hammering. The per-phone and per-IP OTP limits (plan.md 9.4)
    # live in otp_service and are about codes; this one is about requests.
    #
    # `/auth/refresh` and `/auth/logout` are deliberately NOT here, even though
    # plan.md 10 says "/auth/* 20/min/IP". Every page load calls refresh once
    # to restore the session, so behind a carrier NAT or an office router a
    # 20/min bucket on the whole prefix would sign real visitors out for
    # browsing normally - and it did exactly that to the interaction suite,
    # which is 30 page loads in under a minute. Presenting a refresh token is
    # not a credential attempt; it falls under the global bucket.
    ("/api/v1/auth/phone/", 20, 60),
    ("/api/v1/auth/google", 20, 60),
    ("/api/v1/users/me/avatar", 30, 3600),
    # Everything else.
    ("", 300, 60),
)

# Uploads are expensive - each one decodes and re-encodes an image - but they
# are identified by the END of the path, not the start: `/products/{id}/images`
# has a variable in the middle.
#
# This exists because the first version used the prefix `/api/v1/admin/products`
# and therefore throttled every READ of the product table and the review queue
# to sixty an hour. An administrator working through a morning's listings would
# have been locked out of their own panel; the interaction suite hit it in
# under a minute. A limit written for a write path must not cover the reads.
UPLOAD_SUFFIX = "/images"
UPLOAD_RULE = ("uploads", 60, 3600)

# Health probes must never be rate limited: a limiter that takes out the
# readiness endpoint turns a traffic spike into an outage.
EXEMPT = ("/api/v1/healthz", "/api/v1/readyz")

MAX_BODY_BYTES = 10 * 1024 * 1024


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    @staticmethod
    def _client(request: Request) -> str:
        # Behind Caddy the socket address is the proxy's (see api/deps.py).
        forwarded = request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    @staticmethod
    def _rule(path: str) -> tuple[str, int, int]:
        if path.endswith(UPLOAD_SUFFIX):
            return UPLOAD_RULE

        for prefix, limit, window in RULES:
            if path.startswith(prefix):
                return prefix, limit, window
        return "", 300, 60

    def _too_many(self, key: tuple[str, str], limit: int, window: int) -> int | None:
        """Returns the seconds to wait, or None when the request is allowed."""
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > window:
            hits.popleft()

        if len(hits) >= limit:
            return max(1, int(window - (now - hits[0])))

        hits.append(now)
        return None

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        if path in EXEMPT:
            return await call_next(request)

        # Size cap in the application as well as at the proxy (plan.md 10):
        # the app has to be safe when it is run without Caddy in front of it.
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
            return self._error(request, ErrorCode.PAYLOAD_TOO_LARGE, 413)

        prefix, limit, window = self._rule(path)
        retry_after = self._too_many((prefix, self._client(request)), limit, window)
        if retry_after is not None:
            log.warning("rate_limited", path=path, prefix=prefix or "*", limit=limit)
            return self._error(
                request, ErrorCode.RATE_LIMITED, 429, headers={"Retry-After": str(retry_after)}
            )

        return await call_next(request)

    @staticmethod
    def _error(
        request: Request,
        code: ErrorCode,
        status_code: int,
        headers: dict[str, str] | None = None,
    ) -> JSONResponse:
        lang = "en" if request.headers.get("accept-language", "")[:2].lower() == "en" else "az"
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": code.value,
                    "message": translate_error(code.value, lang),
                    "field": None,
                    "details": {},
                }
            },
            headers={"Cache-Control": "no-store", **(headers or {})},
        )
