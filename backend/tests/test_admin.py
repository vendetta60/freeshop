"""Admin panel API (plan.md 6.2, 9.5-9.7, 11).

These target the invariants rather than the happy path: the phone gate on
publishing, two-level categories, the refusal to delete a category that still
holds something, soft delete staying reversible, exactly one main image, and
an upload pipeline that decides what a file is from its bytes.
"""

from __future__ import annotations

import io
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core import otp_inbox
from app.db.models import Category, Product, User
from tests.conftest import build_client

PREFIX = "/api/v1"

ADMIN_PHONE = "+994500000001"
USER_PHONE = "+994501112233"


@pytest.fixture
async def shop(
    db: tuple[object, async_sessionmaker, str], monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> AsyncIterator[AsyncClient]:
    _, maker, _ = db
    async with maker() as session:
        session.add(
            User(
                phone=ADMIN_PHONE,
                phone_verified=True,
                full_name="Admin",
                role="admin",
            )
        )
        session.add(Category(slug="mebel", name_az="Mebel", name_en="Furniture"))
        await session.commit()

    # Uploads land in a throwaway directory, so the suite never writes into
    # the developer's real static/uploads tree.
    async with build_client(db, monkeypatch, upload_dir=tmp_path) as client:
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


async def _admin(client: AsyncClient) -> dict[str, str]:
    return await _sign_in(client, ADMIN_PHONE)


async def _category_id(client: AsyncClient, headers: dict[str, str]) -> int:
    categories = (await client.get(f"{PREFIX}/admin/categories", headers=headers)).json()
    return int(categories[0]["id"])


def _png(size: tuple[int, int] = (40, 30), colour: str = "#3b82f6") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, format="PNG")
    return buffer.getvalue()


async def _create_product(
    client: AsyncClient, headers: dict[str, str], **overrides: object
) -> dict[str, object]:
    payload: dict[str, object] = {
        "title_az": "Qoz ağacından masa",
        "price_minor": 48900,
        "category_id": await _category_id(client, headers),
    }
    payload.update(overrides)
    response = await client.post(f"{PREFIX}/admin/products", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return dict(response.json())


# ---------------------------------------------------------------------------
# Authorisation
# ---------------------------------------------------------------------------
async def test_every_admin_route_rejects_a_normal_user(shop: AsyncClient) -> None:
    """The frontend route guard is UX; this is the control (plan.md 10)."""
    headers = await _sign_in(shop, USER_PHONE)

    for method, path in [
        ("get", "/admin/products"),
        ("post", "/admin/products"),
        ("get", "/admin/categories"),
        ("post", "/admin/categories"),
        ("get", "/admin/users"),
        ("get", "/admin/settings"),
        ("patch", "/admin/settings"),
        ("get", "/admin/stats"),
    ]:
        response = await getattr(shop, method)(
            f"{PREFIX}{path}", headers=headers, **({"json": {}} if method != "get" else {})
        )
        assert response.status_code == 403, f"{method} {path} -> {response.status_code}"
        assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_publishing_requires_a_verified_phone(
    shop: AsyncClient, db: tuple[object, async_sessionmaker, str]
) -> None:
    """plan.md 9.3: admin alone is not enough to put a listing on the site.

    Signing in by OTP proves the number, so the unverified state is arranged
    afterwards - which also exercises the point of the guard: it re-reads the
    user rather than trusting the claims baked into the token.
    """
    admin = await _admin(shop)
    category = await _category_id(shop, admin)

    _, maker, _ = db
    async with maker() as session:
        user = (await session.execute(select(User).where(User.phone == ADMIN_PHONE))).scalar_one()
        user.phone_verified = False
        await session.commit()

    response = await shop.post(
        f"{PREFIX}/admin/products",
        json={"title_az": "Kətan köynək", "price_minor": 4900, "category_id": category},
        headers=admin,
    )
    assert response.status_code == 403
    # A distinct code, so the panel can open the verify modal (plan.md 6.3).
    assert response.json()["error"]["code"] == "PHONE_NOT_VERIFIED"

    # Reading the panel is still allowed; only publishing is gated.
    assert (await shop.get(f"{PREFIX}/admin/products", headers=admin)).status_code == 200


# ---------------------------------------------------------------------------
# Product CRUD
# ---------------------------------------------------------------------------
async def test_create_derives_a_slug_and_reaches_the_public_catalogue(shop: AsyncClient) -> None:
    headers = await _admin(shop)
    product = await _create_product(shop, headers)

    # Folded the same way search is, so the URL and the search index agree.
    assert product["slug"] == "qoz-agacindan-masa"
    assert product["has_en"] is False

    public = (await shop.get(f"{PREFIX}/products/{product['slug']}")).json()
    assert public["title"] == "Qoz ağacından masa"
    assert public["price_minor"] == 48900


async def test_duplicate_titles_get_distinct_slugs(shop: AsyncClient) -> None:
    """Two products may legitimately share a title; the URL must still work."""
    headers = await _admin(shop)
    first = await _create_product(shop, headers)
    second = await _create_product(shop, headers)
    assert first["slug"] == "qoz-agacindan-masa"
    assert second["slug"] == "qoz-agacindan-masa-2"


async def test_update_refreshes_the_search_index(shop: AsyncClient) -> None:
    """A stale folded copy fails silently, which is worse than no search."""
    headers = await _admin(shop)
    product = await _create_product(shop, headers)

    await shop.patch(
        f"{PREFIX}/admin/products/{product['id']}",
        json={"title_az": "Məxmər divan"},
        headers=headers,
    )
    found = (await shop.get(f"{PREFIX}/products", params={"q": "mexmer"})).json()
    assert [item["title"] for item in found["items"]] == ["Məxmər divan"]


async def test_an_explicit_null_clears_the_en_translation(shop: AsyncClient) -> None:
    """Absent means unchanged; null means remove (plan.md 7.3)."""
    headers = await _admin(shop)
    product = await _create_product(shop, headers, title_en="Walnut table")
    assert product["has_en"] is True

    untouched = (
        await shop.patch(
            f"{PREFIX}/admin/products/{product['id']}",
            json={"price_minor": 50000},
            headers=headers,
        )
    ).json()
    assert untouched["title_en"] == "Walnut table"

    cleared = (
        await shop.patch(
            f"{PREFIX}/admin/products/{product['id']}",
            json={"title_en": None},
            headers=headers,
        )
    ).json()
    assert cleared["title_en"] is None
    assert cleared["has_en"] is False

    # EN now falls back to AZ rather than blanking (plan.md 7.3).
    english = (await shop.get(f"{PREFIX}/products/{product['slug']}", params={"lang": "en"})).json()
    assert english["title"] == "Qoz ağacından masa"


async def test_soft_delete_hides_the_product_but_keeps_it_restorable(shop: AsyncClient) -> None:
    headers = await _admin(shop)
    product = await _create_product(shop, headers)

    assert (
        await shop.delete(f"{PREFIX}/admin/products/{product['id']}", headers=headers)
    ).status_code == 204

    assert (await shop.get(f"{PREFIX}/products")).json()["total"] == 0
    assert (await shop.get(f"{PREFIX}/products/{product['slug']}")).status_code == 404

    hidden = (await shop.get(f"{PREFIX}/admin/products", headers=headers)).json()
    assert hidden["total"] == 0
    with_deleted = (
        await shop.get(
            f"{PREFIX}/admin/products", params={"include_deleted": True}, headers=headers
        )
    ).json()
    assert with_deleted["items"][0]["is_deleted"] is True

    restored = (
        await shop.post(f"{PREFIX}/admin/products/{product['id']}/restore", headers=headers)
    ).json()
    assert restored["is_deleted"] is False
    assert (await shop.get(f"{PREFIX}/products")).json()["total"] == 1


async def test_unknown_category_is_a_field_level_422(shop: AsyncClient) -> None:
    headers = await _admin(shop)
    response = await shop.post(
        f"{PREFIX}/admin/products",
        json={"title_az": "Masa", "price_minor": 100, "category_id": 9999},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["field"] == "category_id"


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
async def test_categories_stop_at_two_levels(shop: AsyncClient) -> None:
    headers = await _admin(shop)
    parent = await _category_id(shop, headers)

    child = (
        await shop.post(
            f"{PREFIX}/admin/categories",
            json={"name_az": "Masalar", "parent_id": parent},
            headers=headers,
        )
    ).json()
    assert child["parent_id"] == parent

    third = await shop.post(
        f"{PREFIX}/admin/categories",
        json={"name_az": "Jurnal masaları", "parent_id": child["id"]},
        headers=headers,
    )
    assert third.status_code == 422
    assert third.json()["error"]["details"]["reason"] == "max_depth_2"


async def test_deleting_a_category_is_blocked_while_it_holds_anything(shop: AsyncClient) -> None:
    headers = await _admin(shop)
    parent = await _category_id(shop, headers)
    await _create_product(shop, headers)

    blocked = await shop.delete(f"{PREFIX}/admin/categories/{parent}", headers=headers)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "CATEGORY_NOT_EMPTY"
    assert blocked.json()["error"]["details"]["products"] == 1

    empty = (
        await shop.post(
            f"{PREFIX}/admin/categories", json={"name_az": "Boş kateqoriya"}, headers=headers
        )
    ).json()
    assert (
        await shop.delete(f"{PREFIX}/admin/categories/{empty['id']}", headers=headers)
    ).status_code == 204


async def test_category_edits_reach_the_public_tree(shop: AsyncClient) -> None:
    headers = await _admin(shop)
    parent = await _category_id(shop, headers)
    await shop.patch(
        f"{PREFIX}/admin/categories/{parent}",
        json={"name_az": "Ev mebeli", "name_en": "Home furniture"},
        headers=headers,
    )
    tree = (await shop.get(f"{PREFIX}/categories", params={"lang": "en"})).json()
    assert tree[0]["name"] == "Home furniture"


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------
async def test_upload_re_encodes_and_the_first_image_becomes_main(shop: AsyncClient) -> None:
    headers = await _admin(shop)
    product = await _create_product(shop, headers)

    response = await shop.post(
        f"{PREFIX}/admin/products/{product['id']}/images",
        files=[("files", ("photo.png", _png(), "image/png"))],
        headers=headers,
    )
    assert response.status_code == 201
    image = response.json()[0]
    # Stored as JPEG regardless of what arrived: the original bytes are never
    # served back (plan.md 9.7).
    assert image["url"].startswith("/static/uploads/products/")
    assert image["url"].endswith(".jpg")
    assert image["is_main"] is True
    assert (image["width"], image["height"]) == (40, 30)

    public = (await shop.get(f"{PREFIX}/products/{product['slug']}")).json()
    assert public["image"] == image["url"]


async def test_a_disguised_non_image_is_refused(shop: AsyncClient) -> None:
    """The declared content type is a claim; the magic bytes decide."""
    headers = await _admin(shop)
    product = await _create_product(shop, headers)

    response = await shop.post(
        f"{PREFIX}/admin/products/{product['id']}/images",
        files=[("files", ("payload.png", b"<?php echo 'pwned'; ?>", "image/png"))],
        headers=headers,
    )
    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "UPLOAD_REJECTED"
    assert body["details"]["reason"] == "not_an_image"


async def test_the_per_product_image_cap_holds(shop: AsyncClient) -> None:
    headers = await _admin(shop)
    product = await _create_product(shop, headers)

    files = [("files", (f"p{i}.png", _png(colour=f"#{i}{i}00ff"), "image/png")) for i in range(9)]
    response = await shop.post(
        f"{PREFIX}/admin/products/{product['id']}/images", files=files, headers=headers
    )
    assert response.status_code == 400
    assert response.json()["error"]["details"]["reason"] == "too_many"


async def test_main_image_is_singular_and_survives_deletion(shop: AsyncClient) -> None:
    headers = await _admin(shop)
    product = await _create_product(shop, headers)
    uploaded = (
        await shop.post(
            f"{PREFIX}/admin/products/{product['id']}/images",
            files=[
                ("files", ("a.png", _png(colour="#111111"), "image/png")),
                ("files", ("b.png", _png(colour="#222222"), "image/png")),
            ],
            headers=headers,
        )
    ).json()
    first, second = uploaded[0]["id"], uploaded[1]["id"]

    promoted = (
        await shop.patch(
            f"{PREFIX}/admin/products/{product['id']}/images/{second}",
            json={"is_main": True},
            headers=headers,
        )
    ).json()
    mains = [image["id"] for image in promoted["images"] if image["is_main"]]
    assert mains == [second]

    assert (
        await shop.delete(
            f"{PREFIX}/admin/products/{product['id']}/images/{second}", headers=headers
        )
    ).status_code == 204

    # Deleting the main image must not leave the card with a blank tile.
    remaining = (await shop.get(f"{PREFIX}/admin/products/{product['id']}", headers=headers)).json()
    assert [image["id"] for image in remaining["images"] if image["is_main"]] == [first]


async def test_an_image_belonging_to_another_product_is_a_404(shop: AsyncClient) -> None:
    headers = await _admin(shop)
    mine = await _create_product(shop, headers)
    theirs = await _create_product(shop, headers, title_az="Başqa məhsul")
    image = (
        await shop.post(
            f"{PREFIX}/admin/products/{theirs['id']}/images",
            files=[("files", ("a.png", _png(), "image/png"))],
            headers=headers,
        )
    ).json()[0]

    response = await shop.delete(
        f"{PREFIX}/admin/products/{mine['id']}/images/{image['id']}", headers=headers
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
async def test_settings_round_trip_and_invalidate_the_public_cache(shop: AsyncClient) -> None:
    headers = await _admin(shop)

    defaults = (await shop.get(f"{PREFIX}/admin/settings", headers=headers)).json()
    assert defaults["accent"] == "azure"
    assert defaults["default_lang"] == "az"

    # Read the public contact block first, so a stale cache would be visible.
    assert (await shop.get(f"{PREFIX}/meta/contact")).json()["phone"] == "+994 50 000 00 42"

    updated = await shop.patch(
        f"{PREFIX}/admin/settings",
        json={"values": {"contact_phone": "+994 55 123 45 67", "accent": "bronze"}},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["accent"] == "bronze"

    assert (await shop.get(f"{PREFIX}/meta/contact")).json()["phone"] == "+994 55 123 45 67"


async def test_an_unknown_settings_key_is_refused_not_ignored(shop: AsyncClient) -> None:
    """A silently dropped key looks saved in the panel and does nothing."""
    headers = await _admin(shop)
    response = await shop.patch(
        f"{PREFIX}/admin/settings",
        json={"values": {"totally_made_up": 1}},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"]["unknown_keys"] == ["totally_made_up"]


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
async def test_stats_counts_and_series(shop: AsyncClient) -> None:
    headers = await _admin(shop)
    await _create_product(shop, headers)

    stats = (await shop.get(f"{PREFIX}/admin/stats", headers=headers)).json()
    assert stats["products"] == 1
    assert stats["categories"] == 1
    assert stats["requests_total"] == 0
    assert len(stats["series"]) == 30
    assert stats["series"][-1]["count"] == 0


async def test_users_listing_is_searchable(shop: AsyncClient) -> None:
    await _sign_in(shop, USER_PHONE)
    headers = await _admin(shop)

    everyone = (await shop.get(f"{PREFIX}/admin/users", headers=headers)).json()
    assert everyone["total"] == 2

    filtered = (
        await shop.get(f"{PREFIX}/admin/users", params={"q": "1112233"}, headers=headers)
    ).json()
    assert [u["phone"] for u in filtered["items"]] == [USER_PHONE]


async def test_deleted_products_are_still_countable(shop: AsyncClient) -> None:
    headers = await _admin(shop)
    product = await _create_product(shop, headers)
    await shop.delete(f"{PREFIX}/admin/products/{product['id']}", headers=headers)

    stats = (await shop.get(f"{PREFIX}/admin/stats", headers=headers)).json()
    assert stats["products"] == 0
    assert stats["products_deleted"] == 1


async def test_the_documented_error_envelope_is_in_the_schema(shop: AsyncClient) -> None:
    """Swagger must describe the errors the server actually returns, not
    FastAPI's default HTTPValidationError (plan.md 6.1)."""
    schema = (await shop.get("/openapi.json")).json()
    responses = schema["paths"][f"{PREFIX}/admin/products"]["get"]["responses"]
    assert "403" in responses
    ref = responses["403"]["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("ErrorEnvelope")

    envelope = schema["components"]["schemas"]["ErrorEnvelope"]
    assert set(schema["components"]["schemas"]["ErrorDetail"]["properties"]) == {
        "code",
        "message",
        "field",
        "details",
    }
    assert "error" in envelope["properties"]


async def test_products_are_owned_by_the_admin_who_created_them(
    shop: AsyncClient, db: tuple[object, async_sessionmaker, str]
) -> None:
    headers = await _admin(shop)
    created = await _create_product(shop, headers)

    _, maker, _ = db
    async with maker() as session:
        product = (
            await session.execute(select(Product).where(Product.id == created["id"]))
        ).scalar_one()
        owner = (
            await session.execute(select(User).where(User.id == product.owner_id))
        ).scalar_one()
        assert owner.phone == ADMIN_PHONE


async def test_admin_edited_page_copy_reaches_the_public_config(shop: AsyncClient) -> None:
    """plan.md 7.3: hero, about, contact intro and footer copy are the admin's
    to edit, so the SPA has to read them rather than ship them compiled in."""
    headers = await _admin(shop)
    await shop.patch(
        f"{PREFIX}/admin/settings",
        json={"values": {"hero_title_az": "Yeni başlıq", "hero_title_en": "A new headline"}},
        headers=headers,
    )

    config = (await shop.get(f"{PREFIX}/meta/config")).json()
    assert config["content"]["hero_title"] == {"az": "Yeni başlıq", "en": "A new headline"}
    # Appearance and language travel with it, which is what lets the panel
    # change them without a rebuild.
    assert config["accent"] == "azure"
    assert config["supported_langs"] == ["az", "en"]
