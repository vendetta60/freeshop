"""User submissions and moderation (plan.md D25).

The site exists so people can give away things they no longer use. Anyone
signed in may offer an item; nothing they write reaches the public catalogue
until an administrator has read it.

These tests are about the gate, not the form: what a visitor can see, what a
stranger can put in front of them, and whether a listing that was never
approved can be reached by any other route.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core import otp_inbox
from app.db.models import Category, Product, User
from tests.conftest import build_client

PREFIX = "/api/v1"

ADMIN_PHONE = "+994500000001"
GIVER_PHONE = "+994501112233"


@pytest.fixture
async def shop(
    db: tuple[AsyncEngine, async_sessionmaker, str], monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncClient]:
    _, maker, _ = db
    async with maker() as session:
        session.add(User(phone=ADMIN_PHONE, phone_verified=True, full_name="Admin", role="admin"))
        session.add(Category(slug="mebel", name_az="Mebel"))
        await session.commit()

    async with build_client(db, monkeypatch) as client:
        yield client


async def _sign_in(client: AsyncClient, phone: str) -> dict[str, str]:
    otp_inbox.clear()
    await client.post(f"{PREFIX}/auth/phone/send-otp", json={"phone": phone})
    code = str(otp_inbox.recent()[0]["code"])
    response = await client.post(
        f"{PREFIX}/auth/phone/verify-otp", json={"phone": phone, "code": code}
    )
    client.cookies.clear()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _category_id(client: AsyncClient, headers: dict[str, str]) -> int:
    return int((await client.get(f"{PREFIX}/admin/categories", headers=headers)).json()[0]["id"])


async def _offer(
    client: AsyncClient, headers: dict[str, str], **overrides: object
) -> dict[str, object]:
    admin = await _sign_in(client, ADMIN_PHONE)
    payload: dict[str, object] = {
        "title_az": "Uşaq velosipedi",
        "description_az": "Oğlum böyüyüb, velosiped isə saz vəziyyətdədir.",
        "category_id": await _category_id(client, admin),
    }
    payload.update(overrides)
    response = await client.post(f"{PREFIX}/products", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return dict(response.json())


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------
async def test_a_submission_starts_pending_and_is_invisible(shop: AsyncClient) -> None:
    giver = await _sign_in(shop, GIVER_PHONE)
    listing = await _offer(shop, giver)

    assert listing["status"] == "pending"

    # Not in the catalogue...
    assert (await shop.get(f"{PREFIX}/products")).json()["total"] == 0
    # ...not reachable by its own URL either. A moderation queue whose items
    # are one guessed slug away from the public is not a queue.
    assert (await shop.get(f"{PREFIX}/products/{listing['slug']}")).status_code == 404


async def test_a_pending_listing_cannot_be_added_to_a_cart(shop: AsyncClient) -> None:
    """The id is knowable - it is in the submitter's own listing page. That
    must not be a way to pull an unreviewed item into the request flow."""
    giver = await _sign_in(shop, GIVER_PHONE)
    listing = await _offer(shop, giver)

    response = await shop.post(
        f"{PREFIX}/cart/items", json={"product_id": listing["id"], "quantity": 1}, headers=giver
    )
    assert response.status_code == 404


async def test_approving_puts_it_on_the_site(shop: AsyncClient) -> None:
    giver = await _sign_in(shop, GIVER_PHONE)
    listing = await _offer(shop, giver)
    admin = await _sign_in(shop, ADMIN_PHONE)

    decided = (
        await shop.post(
            f"{PREFIX}/admin/products/{listing['id']}/moderate",
            json={"status": "approved"},
            headers=admin,
        )
    ).json()
    assert decided["status"] == "approved"
    assert decided["reviewed_at"] is not None

    catalogue = (await shop.get(f"{PREFIX}/products")).json()
    assert [item["title"] for item in catalogue["items"]] == ["Uşaq velosipedi"]


async def test_rejecting_keeps_it_off_the_site_and_explains_why(shop: AsyncClient) -> None:
    giver = await _sign_in(shop, GIVER_PHONE)
    listing = await _offer(shop, giver, title_az="iPhone 14 satıram", price_minor=180000)
    admin = await _sign_in(shop, ADMIN_PHONE)

    note = "Bu sayt satış üçün deyil."
    await shop.post(
        f"{PREFIX}/admin/products/{listing['id']}/moderate",
        json={"status": "rejected", "note": note},
        headers=admin,
    )

    assert (await shop.get(f"{PREFIX}/products")).json()["total"] == 0

    # The submitter is told why, on their own listings page.
    mine = (await shop.get(f"{PREFIX}/products/mine", headers=giver)).json()
    assert mine[0]["status"] == "rejected"
    assert mine[0]["moderation_note"] == note


async def test_a_rejection_takes_back_an_approval(shop: AsyncClient) -> None:
    """Moderation is not one-way. Something approved by mistake has to be
    removable without deleting the record."""
    giver = await _sign_in(shop, GIVER_PHONE)
    listing = await _offer(shop, giver)
    admin = await _sign_in(shop, ADMIN_PHONE)

    for decision, expected_total in (("approved", 1), ("rejected", 0), ("approved", 1)):
        await shop.post(
            f"{PREFIX}/admin/products/{listing['id']}/moderate",
            json={"status": decision},
            headers=admin,
        )
        assert (await shop.get(f"{PREFIX}/products")).json()["total"] == expected_total


async def test_only_an_admin_may_moderate(shop: AsyncClient) -> None:
    giver = await _sign_in(shop, GIVER_PHONE)
    listing = await _offer(shop, giver)

    response = await shop.post(
        f"{PREFIX}/admin/products/{listing['id']}/moderate",
        json={"status": "approved"},
        headers=giver,
    )
    assert response.status_code == 403
    # Approving your own listing is the one thing this whole feature exists to
    # prevent.
    assert (await shop.get(f"{PREFIX}/products")).json()["total"] == 0


async def test_pending_is_not_a_status_a_moderator_can_choose(shop: AsyncClient) -> None:
    """A decision is approve or reject. "Put it back in the queue" would leave
    a listing that has been read but carries no record of it."""
    giver = await _sign_in(shop, GIVER_PHONE)
    listing = await _offer(shop, giver)
    admin = await _sign_in(shop, ADMIN_PHONE)

    response = await shop.post(
        f"{PREFIX}/admin/products/{listing['id']}/moderate",
        json={"status": "pending"},
        headers=admin,
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Free items
# ---------------------------------------------------------------------------
async def test_free_is_the_default_and_is_a_real_price(shop: AsyncClient) -> None:
    """Zero is a price, not a missing one (plan.md 0). The submission form does
    not even require the field."""
    giver = await _sign_in(shop, GIVER_PHONE)
    listing = await _offer(shop, giver)

    assert listing["price_minor"] == 0
    assert listing["is_free"] is True

    admin = await _sign_in(shop, ADMIN_PHONE)
    await shop.post(
        f"{PREFIX}/admin/products/{listing['id']}/moderate",
        json={"status": "approved"},
        headers=admin,
    )
    public = (await shop.get(f"{PREFIX}/products")).json()["items"][0]
    assert public["price_minor"] == 0


# ---------------------------------------------------------------------------
# Ownership
# ---------------------------------------------------------------------------
async def test_the_submitter_owns_what_they_offered(
    shop: AsyncClient, db: tuple[AsyncEngine, async_sessionmaker, str]
) -> None:
    giver = await _sign_in(shop, GIVER_PHONE)
    listing = await _offer(shop, giver)

    _, maker, _ = db
    async with maker() as session:
        product = (
            await session.execute(select(Product).where(Product.id == listing["id"]))
        ).scalar_one()
        owner = (
            await session.execute(select(User).where(User.id == product.owner_id))
        ).scalar_one()
        assert owner.phone == GIVER_PHONE


async def test_you_only_see_your_own_listings(shop: AsyncClient) -> None:
    giver = await _sign_in(shop, GIVER_PHONE)
    await _offer(shop, giver)

    stranger = await _sign_in(shop, "+994559998877")
    assert (await shop.get(f"{PREFIX}/products/mine", headers=stranger)).json() == []


async def test_offering_something_requires_a_signed_in_account(shop: AsyncClient) -> None:
    admin = await _sign_in(shop, ADMIN_PHONE)
    response = await shop.post(
        f"{PREFIX}/products",
        json={"title_az": "Stul", "category_id": await _category_id(shop, admin)},
    )
    assert response.status_code == 401


async def test_an_admin_publishing_directly_skips_the_queue(shop: AsyncClient) -> None:
    """The administrator publishing IS the review."""
    admin = await _sign_in(shop, ADMIN_PHONE)
    created = (
        await shop.post(
            f"{PREFIX}/admin/products",
            json={
                "title_az": "Redaksiya məhsulu",
                "price_minor": 0,
                "category_id": await _category_id(shop, admin),
            },
            headers=admin,
        )
    ).json()

    assert created["status"] == "approved"
    assert (await shop.get(f"{PREFIX}/products")).json()["total"] == 1


async def test_the_queue_lists_the_oldest_first(shop: AsyncClient) -> None:
    """Newest-first leaves whoever waited longest at the bottom of the page."""
    giver = await _sign_in(shop, GIVER_PHONE)
    first = await _offer(shop, giver, title_az="Birinci elan")
    second = await _offer(shop, giver, title_az="İkinci elan")

    admin = await _sign_in(shop, ADMIN_PHONE)
    queue = (
        await shop.get(f"{PREFIX}/admin/products", params={"status": "pending"}, headers=admin)
    ).json()

    assert [item["id"] for item in queue["items"]] == [first["id"], second["id"]]
    # The queue shows who offered it, so the reviewer knows who they are
    # replying to.
    assert queue["items"][0]["owner_phone"] == GIVER_PHONE


async def test_stats_count_what_is_waiting(shop: AsyncClient) -> None:
    giver = await _sign_in(shop, GIVER_PHONE)
    await _offer(shop, giver)
    admin = await _sign_in(shop, ADMIN_PHONE)

    stats = (await shop.get(f"{PREFIX}/admin/stats", headers=admin)).json()
    assert stats["products_pending"] == 1
    # `products` counts what a visitor can actually see.
    assert stats["products"] == 0


# ---------------------------------------------------------------------------
# Photos
# ---------------------------------------------------------------------------
def _png(colour: str = "#3b82f6") -> bytes:
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), colour).save(buffer, format="PNG")
    return buffer.getvalue()


async def test_a_giver_can_photograph_their_own_listing(shop: AsyncClient) -> None:
    """A giveaway with no photograph is an advert nobody answers."""
    giver = await _sign_in(shop, GIVER_PHONE)
    listing = await _offer(shop, giver)

    response = await shop.post(
        f"{PREFIX}/products/{listing['id']}/images",
        files=[("files", ("desk.png", _png(), "image/png"))],
        headers=giver,
    )
    assert response.status_code == 201
    image = response.json()[0]
    # Re-encoded by the same pipeline as an admin upload, not a looser one.
    assert image["url"].endswith(".jpg")
    assert image["is_main"] is True

    mine = (await shop.get(f"{PREFIX}/products/mine", headers=giver)).json()
    assert mine[0]["image"] == image["url"]


async def test_you_cannot_photograph_somebody_elses_listing(shop: AsyncClient) -> None:
    giver = await _sign_in(shop, GIVER_PHONE)
    listing = await _offer(shop, giver)

    stranger = await _sign_in(shop, "+994559998877")
    response = await shop.post(
        f"{PREFIX}/products/{listing['id']}/images",
        files=[("files", ("x.png", _png(), "image/png"))],
        headers=stranger,
    )
    # 404, not 403: the endpoint never confirms someone else's id exists.
    assert response.status_code == 404


async def test_the_upload_pipeline_is_not_relaxed_for_givers(shop: AsyncClient) -> None:
    giver = await _sign_in(shop, GIVER_PHONE)
    listing = await _offer(shop, giver)

    response = await shop.post(
        f"{PREFIX}/products/{listing['id']}/images",
        files=[("files", ("payload.png", b"<?php echo 'pwned'; ?>", "image/png"))],
        headers=giver,
    )
    assert response.status_code == 400
    assert response.json()["error"]["details"]["reason"] == "not_an_image"
