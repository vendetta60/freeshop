"""Deterministic, idempotent database seeding (plan.md 8.1).

    python seeds/seed.py --tier demo
    python seeds/seed.py --tier stress --reset

Seed data is part of the product, not a scratch script: it is what gets
demoed, what the performance budgets are measured against, and what makes
layout bugs visible. So it is deterministic (fixed RNG and a fixed epoch -
never datetime.now()), idempotent (upsert on natural keys), and reviewed.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Allow `python seeds/seed.py` from the backend root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import (
    DEFAULT_SETTINGS,
    CartItem,
    Category,
    OrderRequest,
    OrderRequestItem,
    OtpCode,
    Product,
    ProductImage,
    RefreshToken,
    Setting,
    User,
)
from app.db.session import SessionLocal, engine
from seeds.data.catalogue import CATEGORIES, PRODUCTS, photo

# Fixed epoch, never `datetime.now()`: two runs on two machines must produce
# byte-identical rows, or screenshots drift and failures stop reproducing.
SEED_EPOCH = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
RNG = random.Random(1453)

TIERS = ("minimal", "demo", "stress")


def at(days: int = 0, hours: int = 0) -> datetime:
    return SEED_EPOCH + timedelta(days=days, hours=hours)


# ---------------------------------------------------------------------------
# Users - RFC 2606 reserved domain, non-routable phone range. Never seed a
# real person's number: it renders in the admin panel (plan.md 8.1.1 rule 5).
# ---------------------------------------------------------------------------
def user_fixtures(admin_email: str) -> list[dict[str, object]]:
    return [
        {
            "email": admin_email or "admin@example.com",
            "phone": "+994500000001",
            # True so the publish gate (plan.md 9.3) passes with phone auth off.
            "phone_verified": True,
            "full_name": "Mağaza sahibi",
            "role": "admin",
        },
        {
            "email": "aysel@example.com",
            "phone": "+994500000010",
            "phone_verified": True,
            "full_name": "Aysel Məmmədova",
            "role": "user",
        },
        {
            # No name, no avatar: proves every fallback actually works.
            "email": "rashad@example.com",
            "phone": None,
            "phone_verified": False,
            "full_name": None,
            "role": "user",
        },
        {
            # Phone-only: exercises the `email IS NULL` branch.
            "email": None,
            "phone": "+994500000042",
            "phone_verified": True,
            "full_name": "Telefon istifadəçisi",
            "role": "user",
        },
        {
            "email": "nigar@example.com",
            "phone": None,
            "phone_verified": False,
            "full_name": "Nigar Əliyeva",
            "role": "user",
            "preferred_lang": "en",
            "is_active": False,
        },
    ]


async def upsert_settings(session: AsyncSession) -> None:
    existing = {s.key for s in (await session.execute(select(Setting))).scalars()}
    for key, value in DEFAULT_SETTINGS.items():
        if key not in existing:
            session.add(Setting(key=key, value_json=value, created_at=at(), updated_at=at()))


async def upsert_users(session: AsyncSession, tier: str) -> dict[str, User]:
    settings = get_settings()
    fixtures = user_fixtures(settings.admin_email)
    if tier == "minimal":
        fixtures = fixtures[:3]

    by_key: dict[str, User] = {}
    for index, data in enumerate(fixtures):
        key = str(data.get("email") or data.get("phone"))
        stmt = select(User)
        stmt = (
            stmt.where(User.email == data["email"])
            if data.get("email")
            else stmt.where(User.phone == data["phone"])
        )
        user = (await session.execute(stmt)).scalar_one_or_none()
        if user is None:
            user = User(**data, created_at=at(hours=index), updated_at=at(hours=index))  # type: ignore[arg-type]
            session.add(user)
        by_key[key] = user

    await session.flush()
    return by_key


async def upsert_categories(session: AsyncSession) -> dict[str, Category]:
    by_slug: dict[str, Category] = {}

    for order, parent_seed in enumerate(CATEGORIES):
        parent = (
            await session.execute(select(Category).where(Category.slug == parent_seed["slug"]))
        ).scalar_one_or_none()
        if parent is None:
            parent = Category(
                slug=parent_seed["slug"],
                name_az=parent_seed["name_az"],
                name_en=parent_seed["name_en"],
                sort_order=order,
                created_at=at(),
                updated_at=at(),
            )
            session.add(parent)
            await session.flush()
        by_slug[parent.slug] = parent

        for child_index, child in enumerate(parent_seed["children"]):
            existing = (
                await session.execute(select(Category).where(Category.slug == child["slug"]))
            ).scalar_one_or_none()
            if existing is None:
                existing = Category(
                    slug=child["slug"],
                    name_az=child["name_az"],
                    name_en=child["name_en"],
                    parent_id=parent.id,
                    sort_order=child_index,
                    created_at=at(),
                    updated_at=at(),
                )
                session.add(existing)
            by_slug[child["slug"]] = existing

    await session.flush()
    return by_slug


async def upsert_products(
    session: AsyncSession,
    categories: dict[str, Category],
    admin: User,
    tier: str,
) -> dict[str, Product]:
    seeds = PRODUCTS if tier != "minimal" else PRODUCTS[:6]
    by_slug: dict[str, Product] = {}

    for index, data in enumerate(seeds):
        product = (
            await session.execute(select(Product).where(Product.slug == data["slug"]))
        ).scalar_one_or_none()
        if product is None:
            category = categories[data["category"]]
            product = Product(
                slug=data["slug"],
                title_az=data["title_az"],
                title_en=data.get("title_en"),
                description_az=data.get("description_az", ""),
                description_en=data.get("description_en"),
                price_minor=data["price_minor"],
                old_price_minor=data.get("old_price_minor"),
                category_id=category.id,
                stock_status=data.get("stock_status", "available"),
                owner_id=admin.id,
                is_featured=data.get("is_featured", False),
                # The seeded catalogue IS the demo shop, so it is approved.
                # Stated here rather than relied on: the model default is
                # `pending`, so moderation fails closed (plan.md D25).
                status="approved",
                # Descending so "newest" ordering is stable and meaningful.
                created_at=at(days=-index),
                updated_at=at(days=-index),
            )
            product.refresh_search_text()
            session.add(product)
            await session.flush()

            for position, (photo_id, width, height) in enumerate(data.get("images", [])):
                session.add(
                    ProductImage(
                        product_id=product.id,
                        path=photo(photo_id, width, height),
                        width=width,
                        height=height,
                        is_main=position == 0,
                        sort_order=position,
                        created_at=at(),
                        updated_at=at(),
                    )
                )

        by_slug[product.slug] = product

    # The single most valuable fixture (plan.md 8.1.5 #15): a soft-deleted
    # product still referenced by an order request. It is the one path that
    # breaks silently in production and never shows up in manual testing.
    if tier != "minimal":
        ghost = (
            await session.execute(select(Product).where(Product.slug == "silinmis-mehsul"))
        ).scalar_one_or_none()
        if ghost is None:
            ghost = Product(
                slug="silinmis-mehsul",
                title_az="Silinmiş nümunə məhsul",
                title_en="Deleted sample product",
                description_az="Bu məhsul silinib; tarixi sorğularda görünməlidir.",
                price_minor=9900,
                category_id=categories["mebel"].id,
                owner_id=admin.id,
                status="approved",
                deleted_at=at(days=-1),
                created_at=at(days=-20),
                updated_at=at(days=-1),
            )
            session.add(ghost)
            await session.flush()
        by_slug[ghost.slug] = ghost

    await session.flush()
    return by_slug


# Listings waiting on a decision. Seeded because an empty moderation queue
# demos nothing, and because the first thing anyone asks of a review screen is
# "what does it look like with something in it" (plan.md 8.1.1).
SUBMISSIONS: list[dict[str, object]] = [
    {
        "slug": "usaq-velosipedi-16",
        "title_az": "Uşaq velosipedi, 16 düym",
        "title_en": "Children's bicycle, 16 inch",
        "description_az": (
            "Oğlum böyüyüb, velosiped isə saz vəziyyətdədir. Təkərləri yenidir, "
            "rəngi bir-iki yerdə cızılıb. Pulsuz verirəm, özünüz götürməlisiniz."
        ),
        "category": "velosiped",
        "price_minor": 0,
        "status": "pending",
        "days": -2,
    },
    {
        "slug": "kohne-kitab-desti",
        "title_az": "Kitab dəsti, 20 ədəd bədii ədəbiyyat",
        "description_az": (
            "Oxuyub qurtarmışam, rəfdə yer qalmayıb. Hamısı təmiz, cırığı yoxdur. "
            "Kim istəyirsə, pulsuz."
        ),
        "category": "kitab",
        "price_minor": 0,
        "status": "pending",
        "days": -1,
    },
    {
        "slug": "iphone-14-satiram",
        "title_az": "iPhone 14 Pro, 256 GB — təcili satılır",
        "description_az": "Qiymət 1800 AZN, razılaşma yolu ilə. Zəng edin.",
        "category": "telefonlar",
        "price_minor": 180000,
        "status": "rejected",
        "moderation_note": (
            "Bu sayt istifadə olunmayan əşyaları paylaşmaq üçündür, satış elanları "
            "üçün deyil. Pulsuz verəcəyiniz əşyaları yerləşdirə bilərsiniz."
        ),
        "days": -3,
    },
]


async def upsert_submissions(
    session: AsyncSession,
    users: dict[str, User],
    categories: dict[str, Category],
    tier: str,
) -> None:
    """Pending and rejected offers from an ordinary user, not the admin."""
    if tier == "minimal":
        return

    author = users.get("aysel@example.com")
    if author is None:
        return

    for data in SUBMISSIONS:
        slug = str(data["slug"])
        category = categories.get(str(data["category"]))
        if category is None:
            continue

        existing = (
            await session.execute(select(Product).where(Product.slug == slug))
        ).scalar_one_or_none()
        if existing is not None:
            continue

        product = Product(
            slug=slug,
            title_az=str(data["title_az"]),
            title_en=data.get("title_en"),  # type: ignore[arg-type]
            description_az=str(data.get("description_az", "")),
            price_minor=int(data["price_minor"]),  # type: ignore[arg-type]
            category_id=category.id,
            owner_id=author.id,
            status=str(data["status"]),
            moderation_note=data.get("moderation_note"),  # type: ignore[arg-type]
            reviewed_at=at(days=int(data["days"])) if data["status"] != "pending" else None,
            created_at=at(days=int(data["days"])),
            updated_at=at(days=int(data["days"])),
        )
        product.refresh_search_text()
        session.add(product)

    await session.flush()
    print(f"  submissions: {len(SUBMISSIONS)} queued/reviewed offers")


async def upsert_orders(
    session: AsyncSession,
    users: dict[str, User],
    products: dict[str, Product],
    tier: str,
) -> None:
    if tier == "minimal":
        return

    buyer = users.get("aysel@example.com")
    if buyer is None:
        return

    statuses = ["new", "viewed", "completed", "cancelled", "new", "viewed"]
    picks = [
        ["qoz-agacindan-jurnal-masasi"],
        ["divar-saati", "ketan-yastiq-desti"],
        # Contains the soft-deleted product: exercises PRODUCT_UNAVAILABLE and
        # proves the snapshot survives deletion.
        ["silinmis-mehsul", "mis-asma-chiraq"],
        ["yun-xalca"],
        ["bar-ketili", "divar-refi", "ketan-koynek"],
        [p["slug"] for p in PRODUCTS[:6]],  # long request: drawer scrolling
    ]

    for index, (status, slugs) in enumerate(zip(statuses, picks, strict=True)):
        number = f"{get_settings().request_prefix}-2026-{index + 1:04d}"
        existing = (
            await session.execute(select(OrderRequest).where(OrderRequest.request_no == number))
        ).scalar_one_or_none()
        if existing is not None:
            continue

        request = OrderRequest(
            request_no=number,
            user_id=buyer.id,
            status=status,
            contact_phone=buyer.phone or "+994500000010",
            contact_email=buyer.email,
            note=("Rənq seçimi barədə zəng edin. " * 30)[:900] if index == 5 else None,
            total_minor=0,
            created_at=at(days=index),
            updated_at=at(days=index),
        )
        session.add(request)
        await session.flush()

        total = 0
        for slug in slugs:
            product = products.get(slug)
            if product is None:
                continue
            quantity = RNG.randint(1, 3)
            total += product.price_minor * quantity
            session.add(
                OrderRequestItem(
                    order_request_id=request.id,
                    product_id=product.id,
                    title_snapshot=product.title_az,
                    quantity=quantity,
                    price_at_request_minor=product.price_minor,
                    created_at=at(days=index),
                    updated_at=at(days=index),
                )
            )
        request.total_minor = total


async def seed_stress(session: AsyncSession, categories: dict[str, Category], admin: User) -> None:
    """5,000 products, so the plan.md 11 budgets are measured against reality.

    A p95 of 80 ms proven on twelve rows proves nothing.
    """
    existing = (await session.execute(select(func.count()).select_from(Product))).scalar_one()
    target = 5000
    if existing >= target:
        print(f"  stress: {existing} products already present")
        return

    child_slugs = [c.slug for c in categories.values() if c.parent_id is not None]
    words = ["Ağac", "Mis", "Kətan", "Şüşə", "Palıd", "Məxmər", "Keramika", "Dəri"]
    kinds = ["masa", "rəf", "çıraq", "yastıq", "vaza", "güzgü", "kətil", "xalça"]

    for index in range(existing, target):
        slug = f"stress-mehsul-{index}"
        session.add(
            Product(
                slug=slug,
                title_az=f"{RNG.choice(words)} {RNG.choice(kinds)} №{index}",
                description_az="Yük testi üçün yaradılmış nümunə məhsul.",
                price_minor=RNG.randrange(50, 500000, 50),
                category_id=categories[RNG.choice(child_slugs)].id,
                owner_id=admin.id,
                stock_status=RNG.choice(["available", "available", "out_of_stock", "on_order"]),
                status="approved",
                created_at=at(days=-(index % 500)),
                updated_at=at(days=-(index % 500)),
                search_text=f"stress mehsul {index}",
            )
        )
        if index % 500 == 0:
            await session.flush()
    print(f"  stress: seeded up to {target} products")


async def reset(session: AsyncSession) -> None:
    """Drop all seeded rows. Never the default - a stray --reset before a
    demo is the same class of mistake as `docker compose down -v`."""
    for model in (
        OrderRequestItem,
        OrderRequest,
        CartItem,
        ProductImage,
        Product,
        OtpCode,
        RefreshToken,
        User,
        Setting,
    ):
        await session.execute(delete(model))

    # Categories are self-referential with ON DELETE RESTRICT, so children
    # must go before their parents or SQLite refuses the delete.
    await session.execute(delete(Category).where(Category.parent_id.isnot(None)))
    await session.execute(delete(Category))

    await session.flush()
    print("  reset: all seeded rows removed")


async def run(tier: str, do_reset: bool) -> None:
    async with SessionLocal() as session:
        if do_reset:
            await reset(session)

        await upsert_settings(session)
        users = await upsert_users(session, tier)
        categories = await upsert_categories(session)

        admin = next((u for u in users.values() if u.role == "admin"), None)
        if admin is None:
            raise RuntimeError("no admin user seeded")

        products = await upsert_products(session, categories, admin, tier)
        await upsert_submissions(session, users, categories, tier)
        await upsert_orders(session, users, products, tier)

        if tier == "stress":
            await seed_stress(session, categories, admin)

        await session.commit()

        counts = {
            "users": (await session.execute(select(func.count()).select_from(User))).scalar_one(),
            "categories": (
                await session.execute(select(func.count()).select_from(Category))
            ).scalar_one(),
            "products": (
                await session.execute(select(func.count()).select_from(Product))
            ).scalar_one(),
            "images": (
                await session.execute(select(func.count()).select_from(ProductImage))
            ).scalar_one(),
            "requests": (
                await session.execute(select(func.count()).select_from(OrderRequest))
            ).scalar_one(),
            "settings": (
                await session.execute(select(func.count()).select_from(Setting))
            ).scalar_one(),
        }

    await engine.dispose()
    print(f"\nSeed complete (tier={tier})")
    for name, value in counts.items():
        print(f"  {name:<12} {value}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the FreeShop database.")
    parser.add_argument("--tier", choices=TIERS, default="minimal")
    parser.add_argument(
        "--reset", action="store_true", help="delete seeded rows first (destructive)"
    )
    args = parser.parse_args()
    asyncio.run(run(args.tier, args.reset))


if __name__ == "__main__":
    main()
