"""Health probes and public site metadata."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response, status

from app.api.deps import DbSession, Lang
from app.config import get_settings
from app.core.logging import get_logger
from app.db import session as db
from app.schemas.catalogue import ContactOut
from app.schemas.location import PlaceOut, PlacesOut
from app.services import geo, settings_service

router = APIRouter(tags=["meta"])

# Admin-editable page copy the SPA renders (plan.md 7.3). Each has an `_az`
# and an optional `_en` variant in the settings table.
CONTENT_KEYS = ("hero_title", "hero_subtitle", "about", "contact_intro", "footer_note")
log = get_logger(__name__)


@router.get("/healthz", summary="Liveness - process is up, no dependencies touched")
async def healthz() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "app": settings.app_name, "env": settings.env}


@router.get("/readyz", summary="Readiness - database reachable and uploads writable")
async def readyz(response: Response) -> dict[str, Any]:
    settings = get_settings()
    checks: dict[str, bool] = {}

    try:
        checks["database"] = await db.ping()
    except Exception as exc:  # probe must never raise, whatever the driver throws
        log.warning("readyz_database_failed", error=type(exc).__name__)
        checks["database"] = False

    uploads = settings.resolved_upload_dir
    try:
        uploads.mkdir(parents=True, exist_ok=True)
        probe = uploads / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        checks["uploads"] = True
    except OSError as exc:
        log.warning("readyz_uploads_failed", error=type(exc).__name__)
        checks["uploads"] = False

    ready = all(checks.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if ready else "not_ready", "checks": checks}


@router.get("/meta/config", summary="Public runtime configuration for the SPA")
async def public_config(session: DbSession) -> dict[str, Any]:
    """Feature flags and admin-set appearance the frontend needs before it can
    render anything.

    Deliberately excludes anything secret. ``google_enabled`` lets the UI
    disable the Google button with an explanation instead of rendering a
    button that fails on click (plan.md 18/W2). Accent, theme and language
    come from the settings table rather than the build, which is what makes
    them changeable from the admin panel with no rebuild (plan.md 7.3).
    """
    settings = get_settings()
    site = await settings_service.load_all(session)
    enabled = [lang for lang in site.get("enabled_langs", ["az"]) if lang in ("az", "en")] or ["az"]
    default_lang = site.get("default_lang", "az")
    return {
        "app_name": settings.app_name,
        "default_lang": default_lang if default_lang in enabled else enabled[0],
        "supported_langs": enabled,
        "accent": site.get("accent", "azure"),
        "default_theme": site.get("default_theme", "system"),
        "google_enabled": settings.google_configured,
        "phone_auth_enabled": settings.auth_phone_enabled,
        "demo_mode": settings.demo_mode,
        "currency": "AZN",
        # Both languages, unresolved. The client picks by its own language and
        # falls back to AZ - resolving here would mean re-fetching the whole
        # config every time the visitor flips the switch (plan.md 7.3).
        "content": {
            key: {"az": site.get(f"{key}_az", ""), "en": site.get(f"{key}_en", "")}
            for key in CONTENT_KEYS
        },
    }


@router.get("/meta/contact", summary="Seller contact channels")
async def seller_contact(session: DbSession, lang: Lang) -> ContactOut:
    """Read through the settings service so the admin panel can change these
    without a deploy (plan.md 7.3), and so a key that has never been written
    still resolves to its default rather than to a blank."""
    return await settings_service.contact(session, lang)


@router.get("/meta/places", summary="Cities and districts the location picker offers")
async def places(response: Response) -> PlacesOut:
    """The gazetteer, as options.

    Public and static, so it is cached hard: it changes when the source table
    in `services/geo_data.py` changes, which is a deploy, not a request
    (FreeShop_Prompt 1).
    """
    response.headers["Cache-Control"] = "public, max-age=86400"
    cities = geo.known_cities()
    return PlacesOut(
        cities=[PlaceOut(name=c["name"], region=c["region"]) for c in cities],
        districts={
            city["name"]: districts
            for city in cities
            if (districts := geo.districts_of(city["name"]))
        },
    )


@router.get("/meta/radius-options", summary="Radius choices for the nearby filter")
async def radius_options(response: Response) -> dict[str, list[int]]:
    """Served rather than hardcoded in the client so the two cannot drift.

    `null` - "All" - is not in the list: it is the absence of a radius, and
    encoding it as a magic number would put a 0 or a -1 into a query string
    that means something else.
    """
    response.headers["Cache-Control"] = "public, max-age=86400"
    return {"radius_km": list(geo.RADIUS_OPTIONS)}
