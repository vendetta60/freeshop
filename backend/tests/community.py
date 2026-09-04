"""Shared helpers for the community-layer suites (FreeShop_Prompt 18).

Five test files exercise location, needs, messaging, lending and aid, and all
five need the same three things: a seeded board, a signed-in person, and an
approved listing. Written once here rather than five times, because five
copies of a sign-in helper is five places for the auth flow to drift.

Not a conftest: these are functions the suites call explicitly, and a fixture
that silently seeds a board would make each test harder to read, not easier.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core import otp_inbox
from app.db.models import Category, User
from tests.conftest import build_client

PREFIX = "/api/v1"

ADMIN_PHONE = "+994500000001"
GIVER_PHONE = "+994501112233"
SEEKER_PHONE = "+994502223344"
THIRD_PHONE = "+994503334455"

# Two real places, far apart, so a radius test is not measuring rounding.
# Bakı -> Lənkəran is ~204 km; Bakı -> Sumqayıt is ~26 km.
BAKU = "Bakı"
LANKARAN = "Lənkəran"
SUMQAYIT = "Sumqayıt"


@pytest.fixture
async def board(
    db: tuple[AsyncEngine, async_sessionmaker, str], monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncClient]:
    """A client on a board with one admin and two categories."""
    _, maker, _ = db
    async with maker() as session:
        session.add(User(phone=ADMIN_PHONE, phone_verified=True, full_name="Admin", role="admin"))
        session.add(Category(slug="mebel", name_az="Mebel", name_en="Furniture"))
        session.add(Category(slug="uşaq", name_az="Uşaq üçün", name_en="For children"))
        await session.commit()

    async with build_client(db, monkeypatch) as client:
        yield client


async def sign_in(client: AsyncClient, phone: str) -> dict[str, str]:
    """Sign in by OTP and return the bearer header.

    The refresh cookie is cleared afterwards: httpx keeps cookies on the
    client, so without this every later request would carry the LAST person's
    session and an authorisation test would quietly pass for the wrong reason.
    """
    otp_inbox.clear()
    await client.post(f"{PREFIX}/auth/phone/send-otp", json={"phone": phone})
    code = str(otp_inbox.recent()[0]["code"])
    response = await client.post(
        f"{PREFIX}/auth/phone/verify-otp", json={"phone": phone, "code": code}
    )
    assert response.status_code == 200, response.text
    client.cookies.clear()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def category_id(client: AsyncClient, admin: dict[str, str], index: int = 0) -> int:
    rows = (await client.get(f"{PREFIX}/admin/categories", headers=admin)).json()
    return int(rows[index]["id"])


async def set_location(client: AsyncClient, headers: dict[str, str], city: str) -> None:
    response = await client.put(f"{PREFIX}/users/me/location", json={"city": city}, headers=headers)
    assert response.status_code == 200, response.text


async def offer(
    client: AsyncClient,
    headers: dict[str, str],
    admin: dict[str, str],
    *,
    approve: bool = True,
    **overrides: object,
) -> dict[str, object]:
    """Offer a listing and, by default, approve it.

    Approving by default because most tests are about what happens AFTER a
    listing is live; the moderation gate itself has its own suite.
    """
    payload: dict[str, object] = {
        "title_az": "Nərdivan",
        "description_az": "Alüminium nərdivan, üç metr.",
        "category_id": await category_id(client, admin),
    }
    payload.update(overrides)
    response = await client.post(f"{PREFIX}/products", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    listing = dict(response.json())

    if approve:
        approved = await client.post(
            f"{PREFIX}/admin/products/{listing['id']}/moderate",
            json={"status": "approved"},
            headers=admin,
        )
        assert approved.status_code == 200, approved.text
    return listing


async def post_need(
    client: AsyncClient,
    headers: dict[str, str],
    admin: dict[str, str],
    *,
    approve: bool = True,
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {"title": "Nərdivan", "description": "Tavanı boyamaq üçün."}
    payload.update(overrides)
    response = await client.post(f"{PREFIX}/needs", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    need = dict(response.json())

    if approve:
        moderated = await client.post(
            f"{PREFIX}/admin/needs/{need['id']}/moderate",
            json={"status": "approved"},
            headers=admin,
        )
        assert moderated.status_code == 200, moderated.text
    return need


async def request_item(
    client: AsyncClient, headers: dict[str, str], product_id: int, note: str = "Salam"
) -> dict[str, object]:
    """Put a listing in the cart and turn it into a contact request."""
    added = await client.post(
        f"{PREFIX}/cart/items", json={"product_id": product_id}, headers=headers
    )
    assert added.status_code in (200, 201), added.text
    response = await client.post(
        f"{PREFIX}/order-requests",
        json={"contact_phone": "+994500000000", "note": note},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return dict(response.json()["request"])
