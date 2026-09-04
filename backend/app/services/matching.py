"""Connecting things that exist to people who need them (FreeShop_Prompt 6).

DELIBERATELY NOT AI. v1 is three deterministic signals, combined with a
scoring function that fits on a screen:

  * category      - the strongest signal, and the only one a human curated
  * shared words  - on the diacritic-folded text, so "usaq arabasi" matches
                    "Uşaq arabası" (app/core/text.py)
  * distance      - a pushchair 90 km away is not a match, it is a road trip

Everything lives behind two functions so the whole thing can be replaced -
by embeddings, by a search index, by anything - without a caller changing.
That is the reason this module exists at all rather than the rules sitting in
the product router (FreeShop_Prompt 6: "Avoid putting complex matching rules
directly inside API controllers").
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.text import normalise_search
from app.db.models import NeedRequest, Product
from app.services import geo

# How far a match may be before it stops being useful. A generous default:
# the point is to surface demand a giver did not know about, and a slightly
# wide net beats an empty screen.
DEFAULT_RADIUS_KM = 25.0

# Rows pulled from SQL before scoring. The scoring itself is Python (it reads
# text), so the candidate set is bounded rather than the whole table.
CANDIDATE_LIMIT = 300

# Tokens shorter than this carry no signal - "və", "bir", "the" - and matching
# on them would make every listing match every need.
MIN_TOKEN = 3

CATEGORY_WEIGHT = 2.0
TOKEN_WEIGHT = 1.0

# A candidate has to clear this to be shown at all. One shared long word, or
# a category in common. Below that it is a coincidence, not a match.
MIN_SCORE = 1.0


def tokens(text: str | None) -> set[str]:
    """Folded words worth matching on."""
    return {word for word in normalise_search(text).split() if len(word) >= MIN_TOKEN}


def score(
    *,
    same_category: bool,
    left: set[str],
    right: set[str],
    distance_km: float | None,
) -> float:
    """How good a match this is. Higher is better.

    Distance does not add to the score, it DIVIDES it: two candidates with
    the same words should be ordered by which one is walkable, and adding a
    distance term instead would let a far-away perfect title beat a near
    identical one.
    """
    raw = (CATEGORY_WEIGHT if same_category else 0.0) + TOKEN_WEIGHT * len(left & right)
    if raw <= 0:
        return 0.0
    if distance_km is None:
        # No coordinates on one side. Ranked below anything with a known
        # distance rather than dropped: the match may still be exactly right.
        return raw / 2
    # +1 so that a 0 km match is not a division by zero, and so the curve is
    # gentle over the first few kilometres - across town is not a penalty.
    return raw / (1 + distance_km / 10)


def _origin(row: Product | NeedRequest) -> tuple[float, float] | None:
    if row.latitude is None or row.longitude is None:
        return None
    return float(row.latitude), float(row.longitude)


def _distance_between(
    origin: tuple[float, float] | None, other: Product | NeedRequest
) -> float | None:
    if origin is None or other.latitude is None or other.longitude is None:
        return None
    return geo.haversine_km(origin[0], origin[1], float(other.latitude), float(other.longitude))


def _bounded[T: geo.Located](
    stmt: Select[tuple[T]],
    model: type[T],
    origin: tuple[float, float] | None,
    radius_km: float | None,
) -> Select[tuple[T]]:
    """Add the bounding box when there is an origin and a radius to add.

    Without an origin the query is unrestricted geographically - which is
    correct, not a bug: a listing posted by someone who never set a location
    should still be matched on its words.
    """
    if origin is None or radius_km is None:
        return stmt
    return stmt.where(geo.within_bbox(model, origin[0], origin[1], radius_km))


# ---------------------------------------------------------------------------
# Listing -> needs ("4 people nearby are looking for this")
# ---------------------------------------------------------------------------
async def needs_for_product(
    session: AsyncSession,
    product: Product,
    *,
    limit: int = 10,
    radius_km: float | None = DEFAULT_RADIUS_KM,
) -> list[tuple[NeedRequest, float | None, float]]:
    """Open, approved needs this listing could answer.

    Returns (need, distance_km, score) so the caller renders without
    recomputing. The listing's OWN owner is excluded - a person does not need
    to be told they are looking for the thing they just offered.
    """
    origin = _origin(product)

    stmt = select(NeedRequest).where(
        NeedRequest.public(),
        NeedRequest.user_id != product.owner_id,
    )
    stmt = _bounded(stmt, NeedRequest, origin, radius_km)
    stmt = stmt.options(selectinload(NeedRequest.category)).limit(CANDIDATE_LIMIT)

    candidates = list((await session.execute(stmt)).scalars())
    product_tokens = tokens(f"{product.title_az} {product.title_en or ''}")

    return _rank(
        candidates,
        origin=origin,
        radius_km=radius_km,
        category_id=product.category_id,
        subject_tokens=product_tokens,
        text_of=lambda need: need.title,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# Need -> listings ("someone nearby has one of these")
# ---------------------------------------------------------------------------
async def products_for_need(
    session: AsyncSession,
    need: NeedRequest,
    *,
    limit: int = 10,
    radius_km: float | None = DEFAULT_RADIUS_KM,
) -> list[tuple[Product, float | None, float]]:
    """Visible listings that could answer this need."""
    origin = _origin(need)

    stmt = select(Product).where(
        Product.public(),
        Product.owner_id != need.user_id,
        Product.stock_status != "out_of_stock",
    )
    stmt = _bounded(stmt, Product, origin, radius_km)
    stmt = stmt.options(selectinload(Product.images), selectinload(Product.category)).limit(
        CANDIDATE_LIMIT
    )

    candidates = list((await session.execute(stmt)).scalars())
    need_tokens = tokens(need.title)

    return _rank(
        candidates,
        origin=origin,
        radius_km=radius_km,
        category_id=need.category_id,
        subject_tokens=need_tokens,
        text_of=lambda p: f"{p.title_az} {p.title_en or ''}",
        limit=limit,
    )


def _rank[T: (Product, NeedRequest)](
    candidates: list[T],
    *,
    origin: tuple[float, float] | None,
    radius_km: float | None,
    category_id: int | None,
    subject_tokens: set[str],
    text_of: Callable[[T], str],
    limit: int,
) -> list[tuple[T, float | None, float]]:
    """Score, filter and order. Shared by both directions, because the rule
    is symmetric and writing it twice is how the two directions drift."""
    scored: list[tuple[T, float | None, float]] = []
    for candidate in candidates:
        distance = _distance_between(origin, candidate)
        # The bounding box over-includes its corners; the circle is applied
        # here, where the exact distance is known (services/geo.py).
        if radius_km is not None and distance is not None and distance > radius_km:
            continue

        value = score(
            same_category=category_id is not None and candidate.category_id == category_id,
            left=subject_tokens,
            right=tokens(text_of(candidate)),
            distance_km=distance,
        )
        if value < MIN_SCORE:
            continue
        scored.append((candidate, distance, value))

    scored.sort(key=lambda row: (-row[2], row[1] if row[1] is not None else 1e9))
    return scored[:limit]


def _count_of(bucket: dict[str, object]) -> int:
    """The bucket count as an int.

    The buckets are `dict[str, object]` because they mix a label, a count and
    a distance; this is the one place the count is read back, so the narrowing
    lives here rather than as a cast at each use.
    """
    value = bucket["count"]
    return value if isinstance(value, int) else 0


# ---------------------------------------------------------------------------
# Aggregate demand ("9 people nearby need a ladder")
# ---------------------------------------------------------------------------
async def demand_nearby(
    session: AsyncSession,
    *,
    lat: float | None,
    lng: float | None,
    radius_km: float | None = 50.0,
    limit: int = 12,
) -> list[dict[str, object]]:
    """Grouped local demand, as counts only (Rule F).

    IDENTITIES ARE NOT RETURNED. The public answer to "who needs a ladder?"
    is a number; the names behind it become reachable only by opening a
    conversation from the need itself, which is an authorised, one-to-one act.

    Grouping is by folded title rather than by category: "Nərdivan" is the
    thing people recognise, and a category count would say "12 people need
    Home & Garden", which is true and useless.
    """
    stmt = select(NeedRequest).where(NeedRequest.public())
    if lat is not None and lng is not None and radius_km is not None:
        stmt = stmt.where(geo.within_bbox(NeedRequest, lat, lng, radius_km))
    stmt = stmt.options(selectinload(NeedRequest.category)).limit(geo.CANDIDATE_CAP)

    needs = list((await session.execute(stmt)).scalars())

    buckets: dict[str, dict[str, object]] = {}
    for need in needs:
        distance = None
        # Both coordinates are checked, not just the latitude: they are
        # written together by `geo.apply_to`, but a NULL longitude beside a
        # non-NULL latitude is a row this must not crash on.
        if (
            lat is not None
            and lng is not None
            and need.latitude is not None
            and need.longitude is not None
        ):
            distance = geo.haversine_km(lat, lng, float(need.latitude), float(need.longitude))
            if radius_km is not None and distance > radius_km:
                continue

        key = normalise_search(need.title)
        if not key:
            continue
        bucket = buckets.setdefault(
            key,
            {
                "key": key,
                # The first spelling seen becomes the label. Every member of
                # the bucket folds to the same text, so any of them reads
                # correctly to a human.
                "label": need.title,
                "count": 0,
                "category_id": need.category_id,
                "nearest_km": None,
            },
        )
        bucket["count"] = _count_of(bucket) + 1
        if distance is not None:
            current = bucket["nearest_km"]
            if not isinstance(current, float) or distance < current:
                bucket["nearest_km"] = geo.round_distance(distance)

    ranked = sorted(buckets.values(), key=_count_of, reverse=True)
    return ranked[:limit]
