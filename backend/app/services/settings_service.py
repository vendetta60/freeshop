"""Admin-editable site settings (plan.md 7.3, 8).

Every read merges the stored rows over `DEFAULT_SETTINGS`, so a key that has
never been written still resolves - a fresh install is never half-configured,
and adding a new setting needs no migration and no backfill.

The merged map is cached in-process because it is read on nearly every public
request (contact block, hero copy, appearance). The cache is invalidated on
write and cleared by the application factory, so a test that builds a second
app against a second database never inherits the first one's values.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Setting
from app.db.models.setting import DEFAULT_SETTINGS
from app.schemas.catalogue import ContactOut

# Keys the admin panel may write. Anything else in a payload is rejected
# rather than silently stored: an unknown key would be dead weight that no
# reader ever consults, and it is how a typo becomes a bug nobody can see.
WRITABLE_KEYS: frozenset[str] = frozenset(DEFAULT_SETTINGS)

_cache: dict[str, Any] | None = None


def invalidate() -> None:
    global _cache
    _cache = None


async def load_all(session: AsyncSession) -> dict[str, Any]:
    """Defaults with the stored overrides applied."""
    global _cache
    if _cache is not None:
        return _cache

    rows = {s.key: s.value_json for s in (await session.execute(select(Setting))).scalars()}
    merged = {**DEFAULT_SETTINGS, **rows}
    _cache = merged
    return merged


async def get(session: AsyncSession, key: str, default: Any = None) -> Any:
    return (await load_all(session)).get(key, default)


async def update(session: AsyncSession, values: dict[str, Any]) -> dict[str, Any]:
    """Upsert the given keys. Caller commits.

    Unknown keys are dropped by the schema layer before they reach here; this
    second filter exists because the cache would otherwise happily serve
    something the application has no reader for.
    """
    for key, value in values.items():
        if key not in WRITABLE_KEYS:
            continue
        row = (
            await session.execute(select(Setting).where(Setting.key == key))
        ).scalar_one_or_none()
        if row is None:
            session.add(Setting(key=key, value_json=value))
        else:
            row.value_json = value

    await session.flush()
    invalidate()
    return {**DEFAULT_SETTINGS, **values}


async def contact(session: AsyncSession, lang: str) -> ContactOut:
    """The seller's channels, in one place.

    Both the contact page and the order-request confirmation need this, and
    two hand-rolled copies of the same field mapping is how they end up
    disagreeing about which one falls back to AZ.
    """
    rows = await load_all(session)
    suffix = "_en" if lang == "en" else "_az"
    socials = rows.get("socials") or {}
    return ContactOut(
        phone=str(rows.get("contact_phone", "")),
        whatsapp=str(rows.get("whatsapp", "")),
        telegram=str(rows.get("telegram", "")),
        email=str(rows.get("email", "")),
        address=str(rows.get(f"address{suffix}") or rows.get("address_az", "")),
        working_hours=str(rows.get(f"working_hours{suffix}") or rows.get("working_hours_az", "")),
        socials={k: str(v) for k, v in socials.items()},
    )
