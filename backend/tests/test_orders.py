"""Cart and order requests.

The order-request transaction is the payoff of the whole product, so these
tests target what makes it trustworthy: price snapshots that survive a
reprice, refusal to submit unavailable stock, idempotency, and the fact that
one user can never see or touch another's data.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core import otp_inbox
from app.db.models import Category, OrderRequest, Product, Setting, User
from tests.conftest import build_client

PREFIX = "/api/v1"


@pytest.fixture
async def shop(
    db: tuple[object, async_sessionmaker, str], monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncClient]:
    _, maker, _ = db
    async with maker() as session:
        admin = User(
            email="admin@example.com", full_name="Admin", role="admin", phone_verified=True
        )
        session.add(admin)
        await session.flush()

        category = Category(slug="mebel", name_az="Mebel", name_en="Furniture")
        session.add(category)
        await session.flush()

        for slug, title, price in [
            ("masa", "Jurnal masası", 48900),
            ("kreslo", "Kreslo", 67500),
        ]:
            product = Product(
                slug=slug,
                title_az=title,
                description_az="Təsvir",
                price_minor=price,
                category_id=category.id,
                owner_id=admin.id,
                status="approved",
            )
            product.refresh_search_text()
            session.add(product)

        gone = Product(
            slug="silinmis",
            title_az="Silinmiş",
            description_az="",
            price_minor=1000,
            category_id=category.id,
            owner_id=admin.id,
            status="approved",
        )
        gone.refresh_search_text()
        session.add(gone)

        session.add(Setting(key="contact_phone", value_json="+994 50 000 00 42"))
        session.add(Setting(key="whatsapp", value_json="994500000042"))
        await session.commit()

    async with build_client(db, monkeypatch) as client:
        yield client


async def _sign_in(client: AsyncClient, phone: str = "+994501112233") -> dict[str, str]:
    otp_inbox.clear()
    await client.post(f"{PREFIX}/auth/phone/send-otp", json={"phone": phone})
    code = str(otp_inbox.recent()[0]["code"])
    response = await client.post(
        f"{PREFIX}/auth/phone/verify-otp", json={"phone": phone, "code": code}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _product_id(client: AsyncClient, slug: str) -> int:
    return int((await client.get(f"{PREFIX}/products/{slug}")).json()["id"])


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------
async def test_cart_requires_authentication(shop: AsyncClient) -> None:
    """Guests may browse but never build a basket (plan.md D2)."""
    assert (await shop.get(f"{PREFIX}/cart")).status_code == 401
    assert (
        await shop.post(f"{PREFIX}/cart/items", json={"product_id": 1, "quantity": 1})
    ).status_code == 401


async def test_add_and_read_cart(shop: AsyncClient) -> None:
    headers = await _sign_in(shop)
    pid = await _product_id(shop, "masa")

    body = (
        await shop.post(
            f"{PREFIX}/cart/items", json={"product_id": pid, "quantity": 2}, headers=headers
        )
    ).json()
    assert body["item_count"] == 2
    assert body["total_minor"] == 48900 * 2
    assert body["lines"][0]["product"]["slug"] == "masa"


async def test_adding_the_same_product_increments_one_line(shop: AsyncClient) -> None:
    headers = await _sign_in(shop)
    pid = await _product_id(shop, "masa")

    await shop.post(
        f"{PREFIX}/cart/items", json={"product_id": pid, "quantity": 1}, headers=headers
    )
    body = (
        await shop.post(
            f"{PREFIX}/cart/items", json={"product_id": pid, "quantity": 3}, headers=headers
        )
    ).json()

    assert len(body["lines"]) == 1, "a second line for the same product is a duplicate"
    assert body["lines"][0]["quantity"] == 4


async def test_quantity_zero_removes_the_line(shop: AsyncClient) -> None:
    headers = await _sign_in(shop)
    pid = await _product_id(shop, "masa")
    cart = (
        await shop.post(
            f"{PREFIX}/cart/items", json={"product_id": pid, "quantity": 2}, headers=headers
        )
    ).json()
    line_id = cart["lines"][0]["id"]

    body = (
        await shop.patch(f"{PREFIX}/cart/items/{line_id}", json={"quantity": 0}, headers=headers)
    ).json()
    assert body["lines"] == []


async def test_one_user_cannot_touch_anothers_cart(shop: AsyncClient) -> None:
    """IDOR: cart lines are addressed by id, so the query must also filter by
    the caller (plan.md 10)."""
    alice = await _sign_in(shop, "+994501112233")
    pid = await _product_id(shop, "masa")
    cart = (
        await shop.post(
            f"{PREFIX}/cart/items", json={"product_id": pid, "quantity": 1}, headers=alice
        )
    ).json()
    line_id = cart["lines"][0]["id"]

    shop.cookies.clear()
    bob = await _sign_in(shop, "+994559998877")

    assert (
        await shop.patch(f"{PREFIX}/cart/items/{line_id}", json={"quantity": 9}, headers=bob)
    ).status_code == 404
    assert (await shop.delete(f"{PREFIX}/cart/items/{line_id}", headers=bob)).status_code == 404
    assert (await shop.get(f"{PREFIX}/cart", headers=bob)).json()["lines"] == []


async def test_deleted_product_cannot_be_added(
    shop: AsyncClient, db: tuple[object, async_sessionmaker, str]
) -> None:
    headers = await _sign_in(shop)
    pid = await _product_id(shop, "silinmis")

    _, maker, _ = db
    async with maker() as session:
        product = (
            await session.execute(select(Product).where(Product.slug == "silinmis"))
        ).scalar_one()
        product.deleted_at = datetime.now(UTC)
        await session.commit()

    response = await shop.post(
        f"{PREFIX}/cart/items", json={"product_id": pid, "quantity": 1}, headers=headers
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PRODUCT_UNAVAILABLE"


# ---------------------------------------------------------------------------
# Order requests
# ---------------------------------------------------------------------------
async def test_submitting_an_empty_cart_is_rejected(shop: AsyncClient) -> None:
    headers = await _sign_in(shop)
    response = await shop.post(
        f"{PREFIX}/order-requests", json={"contact_phone": "+994501112233"}, headers=headers
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CART_EMPTY"


async def test_submit_creates_a_request_and_clears_the_cart(shop: AsyncClient) -> None:
    headers = await _sign_in(shop)
    pid = await _product_id(shop, "masa")
    await shop.post(
        f"{PREFIX}/cart/items", json={"product_id": pid, "quantity": 2}, headers=headers
    )

    response = await shop.post(
        f"{PREFIX}/order-requests",
        json={"contact_phone": "+994501112233", "note": "Zəng edin"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["request"]["request_no"].startswith("SR-")
    assert body["request"]["total_minor"] == 48900 * 2
    assert body["request"]["items"][0]["quantity"] == 2
    # The confirmation must carry the seller's channels, or "we got it" is
    # useless to the buyer (plan.md 9.1).
    assert body["contact"]["phone"] == "+994 50 000 00 42"

    assert (await shop.get(f"{PREFIX}/cart", headers=headers)).json()["lines"] == []


async def test_request_numbers_are_sequential(shop: AsyncClient) -> None:
    headers = await _sign_in(shop)
    pid = await _product_id(shop, "masa")

    numbers = []
    for _ in range(3):
        await shop.post(
            f"{PREFIX}/cart/items", json={"product_id": pid, "quantity": 1}, headers=headers
        )
        body = (
            await shop.post(
                f"{PREFIX}/order-requests", json={"contact_phone": "+994501112233"}, headers=headers
            )
        ).json()
        numbers.append(body["request"]["request_no"])

    assert numbers == sorted(numbers)
    assert len(set(numbers)) == 3, "request numbers must be unique"


async def test_prices_are_snapshotted_not_referenced(
    shop: AsyncClient, db: tuple[object, async_sessionmaker, str]
) -> None:
    """The whole reason the line stores a price: a later reprice must not
    silently rewrite history (plan.md 9.1)."""
    headers = await _sign_in(shop)
    pid = await _product_id(shop, "masa")
    await shop.post(
        f"{PREFIX}/cart/items", json={"product_id": pid, "quantity": 1}, headers=headers
    )
    await shop.post(
        f"{PREFIX}/order-requests", json={"contact_phone": "+994501112233"}, headers=headers
    )

    _, maker, _ = db
    async with maker() as session:
        product = (await session.execute(select(Product).where(Product.id == pid))).scalar_one()
        product.price_minor = 999999
        await session.commit()

    history = (await shop.get(f"{PREFIX}/order-requests/me", headers=headers)).json()
    assert history[0]["items"][0]["price_minor"] == 48900
    assert history[0]["total_minor"] == 48900


async def test_title_snapshot_survives_deletion(
    shop: AsyncClient, db: tuple[object, async_sessionmaker, str]
) -> None:
    headers = await _sign_in(shop)
    pid = await _product_id(shop, "masa")
    await shop.post(
        f"{PREFIX}/cart/items", json={"product_id": pid, "quantity": 1}, headers=headers
    )
    await shop.post(
        f"{PREFIX}/order-requests", json={"contact_phone": "+994501112233"}, headers=headers
    )

    _, maker, _ = db
    async with maker() as session:
        product = (await session.execute(select(Product).where(Product.id == pid))).scalar_one()
        product.deleted_at = datetime.now(UTC)
        await session.commit()

    history = (await shop.get(f"{PREFIX}/order-requests/me", headers=headers)).json()
    assert history[0]["items"][0]["title"] == "Jurnal masası"
    # No link, because the product is gone - but the record is still readable.
    assert history[0]["items"][0]["product_slug"] is None


async def test_idempotency_key_prevents_duplicates(shop: AsyncClient) -> None:
    """A double-tapped submit button must not produce two requests."""
    headers = await _sign_in(shop)
    pid = await _product_id(shop, "masa")
    await shop.post(
        f"{PREFIX}/cart/items", json={"product_id": pid, "quantity": 1}, headers=headers
    )

    keyed = {**headers, "Idempotency-Key": "submit-once"}
    first = await shop.post(
        f"{PREFIX}/order-requests", json={"contact_phone": "+994501112233"}, headers=keyed
    )
    second = await shop.post(
        f"{PREFIX}/order-requests", json={"contact_phone": "+994501112233"}, headers=keyed
    )

    assert first.status_code == 201
    assert second.status_code == 200, "a replay is not a new resource"
    assert first.json()["request"]["request_no"] == second.json()["request"]["request_no"]

    history = (await shop.get(f"{PREFIX}/order-requests/me", headers=headers)).json()
    assert len(history) == 1


async def test_history_is_scoped_to_the_owner(shop: AsyncClient) -> None:
    alice = await _sign_in(shop, "+994501112233")
    pid = await _product_id(shop, "masa")
    await shop.post(f"{PREFIX}/cart/items", json={"product_id": pid, "quantity": 1}, headers=alice)
    created = (
        await shop.post(
            f"{PREFIX}/order-requests", json={"contact_phone": "+994501112233"}, headers=alice
        )
    ).json()
    request_id = created["request"]["id"]

    shop.cookies.clear()
    bob = await _sign_in(shop, "+994559998877")

    assert (await shop.get(f"{PREFIX}/order-requests/me", headers=bob)).json() == []
    assert (
        await shop.get(f"{PREFIX}/order-requests/me/{request_id}", headers=bob)
    ).status_code == 404


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
async def test_admin_endpoints_reject_a_normal_user(shop: AsyncClient) -> None:
    """The frontend route guard is UX; this is the actual control."""
    headers = await _sign_in(shop)
    assert (await shop.get(f"{PREFIX}/admin/order-requests", headers=headers)).status_code == 403
    assert (await shop.get(f"{PREFIX}/admin/stats", headers=headers)).status_code == 403


async def test_admin_sees_requests_and_can_change_status(
    shop: AsyncClient, db: tuple[object, async_sessionmaker, str]
) -> None:
    buyer = await _sign_in(shop, "+994501112233")
    pid = await _product_id(shop, "masa")
    await shop.post(f"{PREFIX}/cart/items", json={"product_id": pid, "quantity": 1}, headers=buyer)
    await shop.post(
        f"{PREFIX}/order-requests", json={"contact_phone": "+994501112233"}, headers=buyer
    )

    # Promote the caller rather than juggling a second login.
    _, maker, _ = db
    async with maker() as session:
        user = (
            await session.execute(select(User).where(User.phone == "+994501112233"))
        ).scalar_one()
        user.role = "admin"
        await session.commit()

    admin = await _sign_in(shop, "+994501112233")
    listing = (await shop.get(f"{PREFIX}/admin/order-requests", headers=admin)).json()
    assert listing["total"] == 1
    request_id = listing["items"][0]["id"]
    assert listing["items"][0]["status"] == "new"

    updated = (
        await shop.patch(
            f"{PREFIX}/admin/order-requests/{request_id}",
            json={"status": "viewed", "admin_note": "Zəng edildi"},
            headers=admin,
        )
    ).json()
    assert updated["status"] == "viewed"
    assert updated["admin_note"] == "Zəng edildi"

    stats = (await shop.get(f"{PREFIX}/admin/stats", headers=admin)).json()
    assert stats["requests_total"] == 1
    assert stats["requests_new"] == 0


async def test_the_request_actually_persists(
    shop: AsyncClient, db: tuple[object, async_sessionmaker, str]
) -> None:
    """The gap this phase closed: the confirmation used to be invented on the
    client and nothing reached the database."""
    headers = await _sign_in(shop)
    pid = await _product_id(shop, "masa")
    await shop.post(
        f"{PREFIX}/cart/items", json={"product_id": pid, "quantity": 1}, headers=headers
    )
    await shop.post(
        f"{PREFIX}/order-requests", json={"contact_phone": "+994501112233"}, headers=headers
    )

    _, maker, _ = db
    async with maker() as session:
        rows = list((await session.execute(select(OrderRequest))).scalars())
    assert len(rows) == 1
    assert rows[0].total_minor == 48900
