"""Catalogue API against a seeded database."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Category, Product, ProductImage, User
from tests.conftest import build_client

PREFIX = "/api/v1"


@pytest.fixture
async def seeded_client(
    db: tuple[object, async_sessionmaker, str], monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncClient]:
    """A client backed by a small, purpose-built dataset."""
    _, maker, _ = db
    async with maker() as session:
        admin = User(email="admin@example.com", full_name="Admin", role="admin")
        session.add(admin)
        await session.flush()

        parent = Category(slug="ev", name_az="Ev", name_en="Home", sort_order=0)
        session.add(parent)
        await session.flush()
        child = Category(slug="mebel", name_az="Mebel", name_en="Furniture", parent_id=parent.id)
        session.add(child)
        await session.flush()

        visible = Product(
            slug="masa",
            title_az="Jurnal masası",
            title_en="Coffee table",
            description_az="Təsvir",
            price_minor=48900,
            category_id=child.id,
            owner_id=admin.id,
            status="approved",
            is_featured=True,
        )
        # No title_en: must fall back to the Azerbaijani title.
        no_en = Product(
            slug="yastiq",
            title_az="Kətan yastıq",
            description_az="Təsvir",
            price_minor=3200,
            category_id=child.id,
            owner_id=admin.id,
            status="approved",
        )
        deleted = Product(
            slug="silinmis",
            title_az="Silinmiş",
            description_az="",
            price_minor=100,
            category_id=child.id,
            owner_id=admin.id,
            status="approved",
            deleted_at=datetime.now(UTC),
        )
        for item in (visible, no_en, deleted):
            item.refresh_search_text()
        session.add_all([visible, no_en, deleted])
        await session.flush()
        session.add(ProductImage(product_id=visible.id, path="a/b.jpg", is_main=True))
        await session.commit()

    async with build_client(db, monkeypatch) as client:
        yield client


async def test_lists_only_live_products(seeded_client: AsyncClient) -> None:
    body = (await seeded_client.get(f"{PREFIX}/products")).json()
    slugs = [item["slug"] for item in body["items"]]
    assert body["total"] == 2
    assert "silinmis" not in slugs, "soft-deleted products must never be listed"


async def test_soft_deleted_detail_is_404(seeded_client: AsyncClient) -> None:
    response = await seeded_client.get(f"{PREFIX}/products/silinmis")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_english_falls_back_to_azerbaijani(seeded_client: AsyncClient) -> None:
    """The rule that keeps the site usable with zero translated content."""
    response = await seeded_client.get(f"{PREFIX}/products/yastiq?lang=en")
    assert response.json()["title"] == "Kətan yastıq"


async def test_english_uses_the_translation_when_present(seeded_client: AsyncClient) -> None:
    response = await seeded_client.get(f"{PREFIX}/products/masa?lang=en")
    assert response.json()["title"] == "Coffee table"


async def test_parent_category_includes_children(seeded_client: AsyncClient) -> None:
    """Clicking a top-level category must show everything beneath it."""
    body = (await seeded_client.get(f"{PREFIX}/products?category=ev")).json()
    assert body["total"] == 2


async def test_price_sort_ascending(seeded_client: AsyncClient) -> None:
    body = (await seeded_client.get(f"{PREFIX}/products?sort=price_asc")).json()
    prices = [item["price_minor"] for item in body["items"]]
    assert prices == sorted(prices)


async def test_search_matches_title(seeded_client: AsyncClient) -> None:
    body = (await seeded_client.get(f"{PREFIX}/products?q=jurnal")).json()
    assert [item["slug"] for item in body["items"]] == ["masa"]


async def test_search_ignores_diacritics(seeded_client: AsyncClient) -> None:
    """Azerbaijani is routinely typed without diacritics, so "ketan" must find
    "Kətan". This is exactly the case plain SQLite LIKE cannot handle."""
    body = (await seeded_client.get(f"{PREFIX}/products?q=ketan")).json()
    assert [item["slug"] for item in body["items"]] == ["yastiq"]


async def test_category_tree_has_children_and_counts(seeded_client: AsyncClient) -> None:
    tree = (await seeded_client.get(f"{PREFIX}/categories")).json()
    assert len(tree) == 1
    root = tree[0]
    assert root["name"] == "Ev"
    assert [c["name"] for c in root["children"]] == ["Mebel"]
    # The parent count rolls up its children's products.
    assert root["product_count"] == 2


async def test_category_tree_localises(seeded_client: AsyncClient) -> None:
    tree = (await seeded_client.get(f"{PREFIX}/categories?lang=en")).json()
    assert tree[0]["name"] == "Home"


async def test_pagination_reports_pages(seeded_client: AsyncClient) -> None:
    body = (await seeded_client.get(f"{PREFIX}/products?per_page=1")).json()
    assert body["per_page"] == 1
    assert body["pages"] == 2
    assert len(body["items"]) == 1
