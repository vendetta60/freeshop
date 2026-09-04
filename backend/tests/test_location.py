"""Location, proximity and the privacy of coordinates (FreeShop_Prompt 1, 2, 15).

The load-bearing assertion in this file is `test_the_api_never_publishes_
coordinates`. Everything else here is about ranking; that one is about the
promise the feature is built on - that this board can tell you a ladder is
3 km away without telling anybody where you live (Rule B).
"""

from __future__ import annotations

from httpx import AsyncClient

from app.services import geo
from tests.community import (
    ADMIN_PHONE,
    BAKU,
    GIVER_PHONE,
    LANKARAN,
    PREFIX,
    SEEKER_PHONE,
    SUMQAYIT,
    board,
    offer,
    set_location,
    sign_in,
)

__all__ = ["board"]


# ---------------------------------------------------------------------------
# The maths, without a database
# ---------------------------------------------------------------------------
def test_haversine_matches_the_real_distance() -> None:
    """Bakı to Lənkəran is about 204 km by great circle."""
    km = geo.haversine_km(40.4093, 49.8671, 38.7529, 48.8475)
    assert 200 < km < 210


def test_the_bounding_box_never_under_includes() -> None:
    """The box is a PREFILTER, so it may over-include but must never miss.

    A box that is too small silently drops listings at the east and west
    edges of a radius - the failure nobody notices, because the page still
    renders. The longitude span has to widen with latitude for this to hold.
    """
    lat, lng, radius = 40.4, 49.8, 25.0
    _, max_lat, _, max_lng = geo.bbox(lat, lng, radius)
    assert geo.haversine_km(lat, lng, lat, max_lng) >= radius - 0.01
    assert geo.haversine_km(lat, lng, max_lat, lng) >= radius - 0.01


def test_a_place_resolves_to_its_centre_however_it_is_typed() -> None:
    """Diacritics are optional: Azerbaijani is routinely typed without them."""
    folded = geo.resolve("lenkeran")
    exact = geo.resolve("Lənkəran")
    assert folded == exact
    assert folded[1] == "Lənkəran"
    assert folded[5] == "city"


def test_a_district_is_more_precise_than_its_city() -> None:
    _, city, district, lat, lng, precision = geo.resolve("Bakı", "Xətai")
    assert (city, district, precision) == ("Bakı", "Xətai", "district")
    # Not the city centroid - the district has its own.
    assert (lat, lng) != (40.4093, 49.8671)


def test_an_unknown_place_is_kept_but_not_placed() -> None:
    """A village the gazetteer has not heard of must not be a validation
    error: the person still gets to say where they are, they simply cannot
    take part in the nearby sort."""
    region, city, _district, lat, lng, precision = geo.resolve("Filankəs kəndi")
    assert city == "Filankəs kəndi"
    assert (region, lat, lng, precision) == (None, None, None, "none")


def test_distance_is_rounded_before_it_is_published() -> None:
    """Coarse on purpose: a distance quoted to the metre, from enough
    origins, triangulates the thing it was measuring."""
    assert geo.round_distance(3.4123) == 3.4
    assert geo.round_distance(203.71) == 204.0


# ---------------------------------------------------------------------------
# Through the API
# ---------------------------------------------------------------------------
async def test_a_saved_location_is_a_place_name_not_a_position(board: AsyncClient) -> None:
    seeker = await sign_in(board, SEEKER_PHONE)
    await set_location(board, seeker, LANKARAN)

    mine = (await board.get(f"{PREFIX}/users/me/location", headers=seeker)).json()
    assert mine["city"] == "Lənkəran"
    assert mine["label"] == "Lənkəran"
    assert mine["precision"] == "city"
    # Even your OWN location comes back without numbers.
    assert "latitude" not in mine
    assert "longitude" not in mine


async def test_the_api_never_publishes_coordinates(board: AsyncClient) -> None:
    """The privacy contract, asserted against the real payloads.

    Checked over the whole serialised response rather than field by field, so
    a coordinate added to any nested DTO later trips this test.
    """
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    await set_location(board, giver, LANKARAN)
    listing = await offer(board, giver, admin)

    for url in (
        f"{PREFIX}/products",
        f"{PREFIX}/products/{listing['slug']}",
    ):
        body = (await board.get(url)).text
        assert "latitude" not in body, url
        assert "longitude" not in body, url
        # The place itself is public - that is the point.
        assert "Lənkəran" in body, url


async def test_a_listing_inherits_the_givers_location(board: AsyncClient) -> None:
    """The common case costs no extra typing (FreeShop_Prompt 1)."""
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    await set_location(board, giver, LANKARAN)

    listing = await offer(board, giver, admin)
    detail = (await board.get(f"{PREFIX}/products/{listing['slug']}")).json()
    assert detail["location"]["label"] == "Lənkəran"


async def test_an_explicit_place_beats_the_profile_default(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    await set_location(board, giver, LANKARAN)

    listing = await offer(board, giver, admin, city=BAKU, title_az="Masa")
    detail = (await board.get(f"{PREFIX}/products/{listing['slug']}")).json()
    assert detail["location"]["city"] == "Bakı"


async def test_nearby_orders_by_distance_from_the_viewer(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)

    await offer(board, giver, admin, title_az="Uzaq nərdivan", city=LANKARAN)
    await offer(board, giver, admin, title_az="Yaxın nərdivan", city=SUMQAYIT)

    seeker = await sign_in(board, SEEKER_PHONE)
    await set_location(board, seeker, BAKU)

    page = (await board.get(f"{PREFIX}/products", params={"sort": "nearby"}, headers=seeker)).json()

    assert page["applied_sort"] == "nearby"
    assert [item["title"] for item in page["items"]] == ["Yaxın nərdivan", "Uzaq nərdivan"]
    # ~26 km to Sumqayıt, ~204 km to Lənkəran.
    assert page["items"][0]["location"]["distance_km"] < 30
    assert page["items"][1]["location"]["distance_km"] > 190


async def test_a_radius_excludes_what_is_outside_it(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)

    await offer(board, giver, admin, title_az="Uzaq nərdivan", city=LANKARAN)
    await offer(board, giver, admin, title_az="Yaxın nərdivan", city=SUMQAYIT)

    seeker = await sign_in(board, SEEKER_PHONE)
    await set_location(board, seeker, BAKU)

    page = (
        await board.get(
            f"{PREFIX}/products",
            params={"sort": "nearby", "radius_km": 50},
            headers=seeker,
        )
    ).json()

    assert [item["title"] for item in page["items"]] == ["Yaxın nərdivan"]
    assert page["total"] == 1


async def test_nearby_without_a_location_falls_back_rather_than_failing(
    board: AsyncClient,
) -> None:
    """FreeShop_Prompt 2: "do not break the page".

    The request succeeds, the newest come back, and `applied_sort` tells the
    client to explain that a location would improve the results.
    """
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    await offer(board, giver, admin, city=LANKARAN)

    page = (await board.get(f"{PREFIX}/products", params={"sort": "nearby"})).json()
    assert page["applied_sort"] == "newest"
    assert page["total"] == 1


async def test_a_listing_with_no_coordinates_is_not_ranked_but_is_not_lost(
    board: AsyncClient,
) -> None:
    """A village the gazetteer does not know still gets a listing on the
    board - it simply cannot take part in the distance sort."""
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    await offer(board, giver, admin, title_az="Kənd nərdivanı", city="Filankəs kəndi")
    await offer(board, giver, admin, title_az="Bakı nərdivanı", city=BAKU)

    seeker = await sign_in(board, SEEKER_PHONE)
    await set_location(board, seeker, BAKU)

    nearby = (
        await board.get(f"{PREFIX}/products", params={"sort": "nearby"}, headers=seeker)
    ).json()
    assert [item["title"] for item in nearby["items"]] == ["Bakı nərdivanı"]

    everything = (await board.get(f"{PREFIX}/products")).json()
    assert {item["title"] for item in everything["items"]} == {
        "Kənd nərdivanı",
        "Bakı nərdivanı",
    }


async def test_the_picker_options_come_from_the_server(board: AsyncClient) -> None:
    places = (await board.get(f"{PREFIX}/meta/places")).json()
    names = {city["name"] for city in places["cities"]}
    assert {"Bakı", "Lənkəran", "Gəncə"} <= names
    assert "Xətai" in places["districts"]["Bakı"]

    radii = (await board.get(f"{PREFIX}/meta/radius-options")).json()
    assert radii["radius_km"] == list(geo.RADIUS_OPTIONS)


async def test_clearing_your_location_is_as_easy_as_setting_it(board: AsyncClient) -> None:
    seeker = await sign_in(board, SEEKER_PHONE)
    await set_location(board, seeker, LANKARAN)

    cleared = await board.put(f"{PREFIX}/users/me/location", json={"city": ""}, headers=seeker)
    assert cleared.status_code == 200
    assert cleared.json()["label"] is None
    assert cleared.json()["precision"] == "none"
