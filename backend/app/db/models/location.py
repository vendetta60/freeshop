"""Shared location columns (FreeShop_Prompt 1, plan.md 8).

WHY A MIXIN AND NOT A `locations` TABLE:
every entity that has a location has exactly one, it is never shared, and it
is read on every card in every list. A separate table would add a join to the
hottest query in the application to buy nothing but a foreign key. The
columns are identical everywhere because they are declared once, here.

PRIVACY (FreeShop_Prompt 15, Rule B):
`latitude`/`longitude` are the CENTROID of the city or district, not the
person's front door - see `app.services.geo.snap`. They are never serialised
to a client; the public DTOs carry a place label and, at most, a rounded
distance. `location_precision` records which of the two we stored, so a later
migration to exact coordinates can tell the rows apart.

PORTABILITY:
plain FLOAT columns and a bounding-box comparison, no PostGIS types. Moving
to PostgreSQL later means swapping `app.services.geo`'s bbox predicate for
`ST_DWithin`; nothing else in the application touches coordinates.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Float, String
from sqlalchemy.orm import Mapped, mapped_column

# How precisely the stored coordinates locate the item. `none` means we have
# a place name but no usable coordinates, which is a normal state - the
# nearby sort simply cannot rank that row (FreeShop_Prompt 2).
LOCATION_PRECISIONS = ("none", "city", "district")

COUNTRY_DEFAULT = "AZ"


class LocationMixin:
    """country / region / city / district / lat / lng / precision."""

    country: Mapped[str] = mapped_column(String(2), default=COUNTRY_DEFAULT, nullable=False)
    region: Mapped[str | None] = mapped_column(String(80))
    city: Mapped[str | None] = mapped_column(String(80))
    district: Mapped[str | None] = mapped_column(String(80))

    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    location_precision: Mapped[str] = mapped_column(String(10), default="none", nullable=False)

    @property
    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    def place_label(self) -> str | None:
        """What a visitor is shown: "Lənkəran" or "Lənkəran, Bakı".

        District first, city second, and never the region alone - "Aran" tells
        nobody whether a handover is practical, which is the only question the
        label exists to answer (Rule B).
        """
        parts = [p for p in (self.district, self.city) if p]
        return ", ".join(parts) if parts else (self.region or None)


def location_constraints(table: str) -> tuple[CheckConstraint, ...]:
    """The check constraints every located table carries.

    A function rather than `__table_args__` on the mixin because constraint
    names must be unique per table, and a mixin that produced the same name
    four times would fail at metadata creation.
    """
    return (
        CheckConstraint(
            "location_precision IN ('none','city','district')",
            name=f"{table}_precision_valid",
        ),
        CheckConstraint(
            "latitude IS NULL OR (latitude BETWEEN -90 AND 90)",
            name=f"{table}_latitude_range",
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude BETWEEN -180 AND 180)",
            name=f"{table}_longitude_range",
        ),
    )
