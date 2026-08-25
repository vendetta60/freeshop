"""Application factory.

Assembly order matters: settings are validated first (so a misconfigured
production instance fails at boot, not at request time), then logging, then
middleware, then routers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.api.v1 import api_router
from app.config import Settings, get_settings, set_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging, get_logger
from app.core.rate_limit import RateLimitMiddleware

API_PREFIX = "/api/v1"

log = get_logger(__name__)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply the baseline security headers to every response (plan.md 10)."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.resolved_upload_dir.mkdir(parents=True, exist_ok=True)
    log.info(
        "startup",
        app=settings.app_name,
        env=settings.env,
        google_configured=settings.google_configured,
        phone_auth=settings.auth_phone_enabled,
        otp_channel=settings.otp_channel,
    )
    if settings.demo_mode and settings.is_production:
        # Loud, because it is a deliberately weakened production posture.
        log.warning(
            "demo_mode_enabled",
            detail=(
                "DEMO_MODE=true: the console OTP channel is permitted under "
                "ENV=production. Verification codes appear in this log. Safe only "
                "on a local, non-public instance - never on the internet."
            ),
        )

    from app.services import otp_service

    if settings.is_production and (
        settings.otp_max_sends_per_phone > otp_service.MAX_SENDS_PER_PHONE
        or settings.otp_max_sends_per_ip > otp_service.MAX_SENDS_PER_IP
    ):
        # Loud, because a loosened OTP limit in production is somebody else's
        # SMS bill (plan.md 9.4). Raised deliberately for a shared demo
        # machine; never meant to survive into a real deployment.
        log.warning(
            "otp_limits_relaxed",
            per_phone=settings.otp_max_sends_per_phone,
            per_ip=settings.otp_max_sends_per_ip,
            detail="OTP send limits are above the plan.md 9.4 defaults under ENV=production",
        )

    if not settings.google_configured:
        # Expected during early development - state it once, clearly, rather
        # than failing mysteriously on the first sign-in attempt.
        log.warning(
            "google_oauth_not_configured",
            detail="GOOGLE_CLIENT_ID is empty; /auth/google returns GOOGLE_NOT_CONFIGURED",
        )
    yield
    from app.db.session import dispose_engine

    await dispose_engine()
    log.info("shutdown")


def create_app(settings: Settings | None = None) -> FastAPI:
    # Install it globally, so every service that calls get_settings() sees the
    # same configuration this app was built with rather than the ambient .env.
    if settings is not None:
        set_settings(settings)
    settings = settings or get_settings()
    configure_logging()

    # Site settings are cached in-process (services/settings_service.py).
    # A second app - a test, or a reload - must not inherit the first
    # one's values from a database it is no longer talking to.
    from app.services import settings_service

    settings_service.invalidate()

    app = FastAPI(
        title=f"{settings.app_name} API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
        openapi_url="/openapi.json" if not settings.is_production else None,
    )

    app.add_middleware(SecurityHeadersMiddleware)

    # Rate limits and the body-size cap (plan.md 10).
    #
    # Counters live on the middleware instance, so every app - including every
    # test app - starts with empty buckets. `env=test` switches it off as an
    # escape hatch for a future test that legitimately needs hundreds of
    # requests; the suite as it stands runs with it on.
    if settings.env != "test":
        app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept-Language", "Idempotency-Key"],
        expose_headers=["ETag"],
        max_age=600,
    )

    register_error_handlers(app)
    app.include_router(api_router, prefix=API_PREFIX)

    # ---- Development / demo routes ----------------------------------------
    # Still structural, never a runtime branch inside a handler (plan.md 9.11).
    # DEMO_MODE extends this to the local production stack, because a demo
    # where the verification code is unreachable is not a demo - the operator
    # has already opted in explicitly and startup warns about it.
    if settings.is_development or settings.demo_mode:
        from app.api import dev

        app.include_router(dev.router, prefix=API_PREFIX)

    # Uploaded images. In Docker, Caddy serves these directly and this mount
    # is only a local-dev convenience.
    app.mount(
        "/static/uploads",
        StaticFiles(directory=settings.resolved_upload_dir, check_dir=False),
        name="uploads",
    )

    return app


app = create_app()
