"""Distance, bounding boxes and place resolution (FreeShop_Prompt 1, 2).

THE ALGORITHM, STATED ONCE:

  1. SQL narrows to a bounding box around the origin. A box is four
     comparisons on two indexed FLOAT columns - portable, and the only part
     of this that a database can do well without PostGIS.
  2. Python computes the exact Haversine distance for the rows that survive,
     drops the corners of the box that fall outside the circle, and sorts.

WHY NOT HAVERSINE IN SQL:
SQLite only has `acos`, `cos` and `radians` when it was compiled with
SQLITE_ENABLE_MATH_FUNCTIONS. That is true of the interpreter this was
written on and false of plenty of others, and a nearby sort that works on one
machine and raises `no such function: acos` on another is worse than one that
is merely approximate in its first pass. The box is exact as a filter (it can
only over-include, never under-include), so correctness lives in step 2 where
it is portable.

  ponytail: bbox prefilter + in-Python Haversine ranking. The ceiling is
  CANDIDATE_CAP rows inside one radius; beyond that the ranking is over a
  truncated candidate set. Upgrade path is PostGIS ST_DWithin + ORDER BY
  distance, which replaces `within_bbox` and `rank_by_distance` and nothing
  else.
"""

from __future__ import annotations

from math import asin, cos, degrees, radians, sin, sqrt
from typing import Any, Protocol

from sqlalchemy import ColumnElement, and_, or_

from app.core.text import normalise_search
from app.services.geo_data import CITIES, CITY_INDEX, DISTRICT_INDEX, DISTRICTS

EARTH_RADIUS_KM = 6371.0088

# The radius options offered in the UI (FreeShop_Prompt 2). `None` is "All".
RADIUS_OPTIONS: tuple[int, ...] = (5, 10, 25, 50, 100)
MAX_RADIUS_KM = 500

# How many boxed rows are ranked in Python before the list is truncated.
# Sized so a whole city's listings fit comfortably; see the ponytail note.
CANDIDATE_CAP = 2000


class Located(Protocol):
    """Anything carrying the LocationMixin columns."""

    latitude: Any
    longitude: Any


# ---------------------------------------------------------------------------
# Distance
# ---------------------------------------------------------------------------
def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometres.

    >>> round(haversine_km(40.4093, 49.8671, 38.7529, 48.8475))
    203
    """
    p1, p2 = radians(lat1), radians(lat2)
    d_lat = p2 - p1
    d_lng = radians(lng2 - lng1)
    h = sin(d_lat / 2) ** 2 + cos(p1) * cos(p2) * sin(d_lng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(h))


def bbox(lat: float, lng: float, radius_km: float) -> tuple[float, float, float, float]:
    """(min_lat, max_lat, min_lng, max_lng) enclosing the circle.

    The longitude span widens with latitude, which is why it is divided by
    cos(lat) rather than reused from the latitude span. At Azerbaijani
    latitudes that is a 30% difference - big enough that ignoring it would
    quietly drop listings from the east and west edges of a radius.
    """
    lat_span = degrees(radius_km / EARTH_RADIUS_KM)
    # Guard against the poles, where cos(lat) tends to zero and the span
    # explodes. Nothing in this application is near them, but a ZeroDivision
    # in a sort is a 500 for a user who typed a silly latitude.
    scale = max(cos(radians(lat)), 0.01)
    lng_span = lat_span / scale
    return (
        max(lat - lat_span, -90.0),
        min(lat + lat_span, 90.0),
        lng - lng_span,
        lng + lng_span,
    )


def within_bbox(
    model: type[Located], lat: float, lng: float, radius_km: float
) -> ColumnElement[bool]:
    """A SQL predicate for "possibly within `radius_km`".

    Over-includes the corners of the box; `rank_by_distance` removes them.
    Rows with no coordinates are excluded - they cannot be ranked, and a row
    silently sorted to the top because NULL compared oddly is the bug this
    explicitness prevents.
    """
    min_lat, max_lat, min_lng, max_lng = bbox(lat, lng, radius_km)
    return and_(
        model.latitude.is_not(None),
        model.longitude.is_not(None),
        model.latitude.between(min_lat, max_lat),
        model.longitude.between(min_lng, max_lng),
    )


def has_coordinates(model: type[Located]) -> ColumnElement[bool]:
    return and_(model.latitude.is_not(None), model.longitude.is_not(None))


def rank_by_distance[T: Located](
    rows: list[T],
    lat: float,
    lng: float,
    *,
    radius_km: float | None = None,
) -> list[tuple[T, float]]:
    """Exact distances, nearest first, circle applied.

    Returns pairs so the caller can put the number on the DTO without
    computing it a second time.
    """
    ranked: list[tuple[T, float]] = []
    for row in rows[:CANDIDATE_CAP]:
        if row.latitude is None or row.longitude is None:
            continue
        distance = haversine_km(lat, lng, row.latitude, row.longitude)
        if radius_km is not None and distance > radius_km:
            continue
        ranked.append((row, distance))
    ranked.sort(key=lambda pair: pair[1])
    return ranked


def round_distance(km: float) -> float:
    """The number a client is allowed to see.

    One decimal below 10 km, whole kilometres above. Deliberately coarse:
    a distance quoted to the metre, from enough origins, triangulates the
    thing it was measuring (FreeShop_Prompt 15).
    """
    return round(km, 1) if km < 10 else float(round(km))


# ---------------------------------------------------------------------------
# Place resolution
# ---------------------------------------------------------------------------
def resolve(
    city: str | None, district: str | None = None
) -> tuple[str | None, str | None, str | None, float | None, float | None, str]:
    """Normalise a typed place into (region, city, district, lat, lng, precision).

    An unrecognised city is NOT an error: the person still gets to say where
    they are, the row simply has no coordinates and cannot take part in the
    nearby sort (`precision='none'`). Refusing the listing instead would
    punish someone for living in a village this table has not heard of.
    """
    if not city or not city.strip():
        return None, None, None, None, None, "none"

    typed_city = city.strip()[:80]
    canonical = CITY_INDEX.get(normalise_search(typed_city))
    if canonical is None:
        # Keep the name, drop the claim to coordinates.
        return None, typed_city, (district or "").strip()[:80] or None, None, None, "none"

    region, lat, lng = CITIES[canonical]
    typed_district = (district or "").strip()[:80] or None

    if typed_district:
        known = DISTRICT_INDEX.get(canonical, {}).get(normalise_search(typed_district))
        if known is not None:
            d_lat, d_lng = DISTRICTS[canonical][known]
            return region, canonical, known, d_lat, d_lng, "district"

    # A district we do not know: keep the label, use the city centroid. The
    # label is still useful to a human arranging a handover even when it
    # buys no precision.
    return region, canonical, typed_district, lat, lng, "city"


def known_cities() -> list[dict[str, str]]:
    """The picker's options, sorted for a human reader.

    Sorted with the Azerbaijani alphabet folded away rather than by raw code
    point, so ə, ı, ö and ü are not exiled to the end of the list.
    """
    return [
        {"name": name, "region": region}
        for name, (region, _lat, _lng) in sorted(
            CITIES.items(), key=lambda pair: normalise_search(pair[0])
        )
    ]


def districts_of(city: str | None) -> list[str]:
    if not city:
        return []
    canonical = CITY_INDEX.get(normalise_search(city))
    if canonical is None:
        return []
    return sorted(DISTRICTS.get(canonical, {}), key=normalise_search)


def apply_to(target: Any, data: dict[str, Any]) -> None:
    """Write a resolved place onto any LocationMixin row.

    One writer for four tables, so the snap-to-centroid rule cannot be
    implemented correctly in three of them and forgotten in the fourth.
    """
    region, city, district, lat, lng, precision = resolve(data.get("city"), data.get("district"))
    target.country = (data.get("country") or "AZ").upper()[:2]
    # An explicit region wins only when the gazetteer has no opinion.
    target.region = region or ((data.get("region") or "").strip()[:80] or None)
    target.city = city
    target.district = district
    target.latitude = lat
    target.longitude = lng
    target.location_precision = precision


def copy_from(target: Any, source: Any) -> None:
    """Prefill one row's location from another (a user's default onto a new
    listing, FreeShop_Prompt 1)."""
    for field in (
        "country",
        "region",
        "city",
        "district",
        "latitude",
        "longitude",
        "location_precision",
    ):
        setattr(target, field, getattr(source, field))


def origin_or_none(
    lat: float | None, lng: float | None, user: Any | None
) -> tuple[float, float] | None:
    """Where "nearby" is measured from.

    Explicit coordinates win, then the signed-in user's saved default
    (FreeShop_Prompt 2). Returns None when neither is available, which is the
    caller's cue to fall back to newest-first rather than to fail.
    """
    if lat is not None and lng is not None:
        return lat, lng
    if user is not None and user.latitude is not None and user.longitude is not None:
        return float(user.latitude), float(user.longitude)
    return None


def city_matches(model: type[Any], city: str) -> ColumnElement[bool]:
    """Fallback locality filter for rows with no coordinates.

    Used when someone wants "things in Lənkəran" and the row was posted from
    a village the gazetteer does not know: the name still matches even though
    the distance cannot be computed.
    """
    folded = normalise_search(city)
    canonical = CITY_INDEX.get(folded)
    names = {city.strip(), canonical} - {None, ""}
    return or_(*[model.city == name for name in names]) if names else model.city == city
