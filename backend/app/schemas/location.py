"""Location DTOs (FreeShop_Prompt 1, 15).

THE PRIVACY BOUNDARY IS THIS FILE. `LocationOut` has no latitude and no
longitude, and that is not an oversight to be corrected later - it is the
contract. A client learns a place NAME and, when it asked from somewhere, a
ROUNDED distance. Nothing that composes into a position.

`OwnLocationOut` is the one exception and still carries no coordinates: its
extra field is `precision`, so a person can see whether the site knows their
district or only their city, which is the thing they might want to change.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from app.db.models.location import LocationMixin


class LocationIn(BaseModel):
    """What a client may send. Coordinates are deliberately NOT accepted.

    The server resolves a place name to a centroid itself (services/geo.py).
    Accepting a latitude would mean accepting somebody's doorstep, and once
    it is in the database the privacy property is gone whatever the API does
    afterwards.
    """

    city: Annotated[str | None, Field(default=None, max_length=80)] = None
    district: Annotated[str | None, Field(default=None, max_length=80)] = None
    country: Annotated[str | None, Field(default=None, max_length=2)] = None
    region: Annotated[str | None, Field(default=None, max_length=80)] = None


class LocationOut(BaseModel):
    """A place, as everyone else sees it."""

    country: str
    region: str | None = None
    city: str | None = None
    district: str | None = None
    label: str | None = None
    #  Present only when the caller supplied an origin. Rounded by
    #  `geo.round_distance` before it reaches this model.
    distance_km: float | None = None

    @classmethod
    def of(cls, row: LocationMixin, distance_km: float | None = None) -> LocationOut:
        return cls(
            country=row.country,
            region=row.region,
            city=row.city,
            district=row.district,
            label=row.place_label(),
            distance_km=distance_km,
        )


class OwnLocationOut(LocationOut):
    """Your own saved location, with how precisely it is stored."""

    precision: str

    @classmethod
    def of_own(cls, row: LocationMixin) -> OwnLocationOut:
        return cls(
            country=row.country,
            region=row.region,
            city=row.city,
            district=row.district,
            label=row.place_label(),
            precision=row.location_precision,
        )


class PlaceOut(BaseModel):
    """One option in the location picker."""

    name: str
    region: str


class PlacesOut(BaseModel):
    cities: list[PlaceOut]
    #  Districts, keyed by city. Only cities that have them appear.
    districts: dict[str, list[str]]
