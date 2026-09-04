"""The needs board and the conversion of lost requests into demand
(FreeShop_Prompt 4, 5; Rules C and F).

Two properties matter more than the CRUD here:

  * A need is invisible until an administrator reads it, and a hidden need is
    a 404 rather than a 403 - confirming that need 41 exists but is hidden
    says something about somebody's circumstances they did not publish.

  * Ten people ask for one ladder; one gets it. The other nine are recorded,
    not deleted, and become public demand only if they say so.
"""

from __future__ import annotations

from httpx import AsyncClient

from tests.community import (
    ADMIN_PHONE,
    BAKU,
    GIVER_PHONE,
    LANKARAN,
    PREFIX,
    SEEKER_PHONE,
    SUMQAYIT,
    THIRD_PHONE,
    board,
    offer,
    post_need,
    request_item,
    set_location,
    sign_in,
)

__all__ = ["board"]


# ---------------------------------------------------------------------------
# Posting and moderation
# ---------------------------------------------------------------------------
async def test_a_need_starts_pending_and_is_invisible(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    seeker = await sign_in(board, SEEKER_PHONE)

    need = await post_need(board, seeker, admin, approve=False)
    assert need["moderation_status"] == "pending"

    board_page = (await board.get(f"{PREFIX}/needs")).json()
    assert board_page["total"] == 0

    # A stranger cannot reach it by guessing the id.
    assert (await board.get(f"{PREFIX}/needs/{need['id']}")).status_code == 404
    # Its author can always see their own.
    assert (await board.get(f"{PREFIX}/needs/{need['id']}", headers=seeker)).status_code == 200


async def test_approving_puts_a_need_on_the_board(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    seeker = await sign_in(board, SEEKER_PHONE)
    need = await post_need(board, seeker, admin)

    listed = (await board.get(f"{PREFIX}/needs")).json()
    assert [row["id"] for row in listed["items"]] == [need["id"]]


async def test_a_rejection_carries_its_reason_back_to_the_author(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    seeker = await sign_in(board, SEEKER_PHONE)
    need = await post_need(board, seeker, admin, approve=False)

    await board.post(
        f"{PREFIX}/admin/needs/{need['id']}/moderate",
        json={"status": "rejected", "note": "Bu, ehtiyac deyil - satış elanıdır."},
        headers=admin,
    )

    mine = (await board.get(f"{PREFIX}/needs/mine", headers=seeker)).json()
    assert mine[0]["moderation_status"] == "rejected"
    assert "satış elanıdır" in mine[0]["moderation_note"]


async def test_only_an_admin_may_moderate_a_need(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    seeker = await sign_in(board, SEEKER_PHONE)
    need = await post_need(board, seeker, admin, approve=False)

    response = await board.post(
        f"{PREFIX}/admin/needs/{need['id']}/moderate",
        json={"status": "approved"},
        headers=seeker,
    )
    assert response.status_code == 403


async def test_the_board_never_names_who_needs_something(board: AsyncClient) -> None:
    """Rule F. The queue names them; the public board must not."""
    admin = await sign_in(board, ADMIN_PHONE)
    seeker = await sign_in(board, SEEKER_PHONE)
    await board.patch(f"{PREFIX}/users/me", json={"full_name": "Aysel Məmmədova"}, headers=seeker)
    await post_need(board, seeker, admin)

    public = (await board.get(f"{PREFIX}/needs")).text
    assert "Aysel" not in public
    assert "user_id" not in public

    queue = (await board.get(f"{PREFIX}/admin/needs", headers=admin)).text
    assert "Aysel" in queue


async def test_posting_a_need_needs_no_verified_phone(board: AsyncClient) -> None:
    """Unlike offering an item.

    Publishing a listing is a promise to meet a stranger; admitting you need
    a pushchair is not, and requiring a verified number would exclude exactly
    the people this board is for.
    """
    admin = await sign_in(board, ADMIN_PHONE)
    seeker = await sign_in(board, SEEKER_PHONE)
    response = await board.post(f"{PREFIX}/needs", json={"title": "Uşaq arabası"}, headers=seeker)
    assert response.status_code == 201
    assert admin  # the fixture's admin exists; nothing about it gates this


async def test_posting_a_need_still_requires_an_account(board: AsyncClient) -> None:
    assert (await board.post(f"{PREFIX}/needs", json={"title": "Masa"})).status_code == 401


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
async def test_the_owner_can_close_and_reopen_their_need(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    seeker = await sign_in(board, SEEKER_PHONE)
    need = await post_need(board, seeker, admin)

    closed = await board.post(
        f"{PREFIX}/needs/{need['id']}/status", json={"status": "fulfilled"}, headers=seeker
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "fulfilled"

    # A fulfilled need leaves the public board.
    assert (await board.get(f"{PREFIX}/needs")).json()["total"] == 0

    reopened = await board.post(
        f"{PREFIX}/needs/{need['id']}/status", json={"status": "open"}, headers=seeker
    )
    assert reopened.status_code == 200
    assert (await board.get(f"{PREFIX}/needs")).json()["total"] == 1


async def test_an_invalid_lifecycle_move_is_refused_with_its_reason(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    seeker = await sign_in(board, SEEKER_PHONE)
    need = await post_need(board, seeker, admin)

    # open -> expired is not the owner's to make; expiry is the clock's.
    # 409, not 422: the payload is well formed, the STATE refuses it.
    response = await board.post(
        f"{PREFIX}/needs/{need['id']}/status", json={"status": "expired"}, headers=seeker
    )
    assert response.status_code == 409
    details = response.json()["error"]["details"]
    assert details["reason"] == "invalid_transition"
    # The error names what WOULD be allowed, so a client can render the
    # buttons that will actually work.
    assert set(details["allowed"]) == {"partially_fulfilled", "fulfilled", "closed"}


async def test_you_cannot_edit_somebody_elses_need(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    seeker = await sign_in(board, SEEKER_PHONE)
    need = await post_need(board, seeker, admin)

    stranger = await sign_in(board, THIRD_PHONE)
    edited = await board.patch(
        f"{PREFIX}/needs/{need['id']}", json={"title": "Başqa şey"}, headers=stranger
    )
    assert edited.status_code == 404


# ---------------------------------------------------------------------------
# Nearby and aggregate demand
# ---------------------------------------------------------------------------
async def test_needs_can_be_filtered_by_distance(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    near = await sign_in(board, SEEKER_PHONE)
    far = await sign_in(board, THIRD_PHONE)

    await post_need(board, near, admin, title="Yaxın nərdivan", city=SUMQAYIT)
    await post_need(board, far, admin, title="Uzaq nərdivan", city=LANKARAN)

    viewer = await sign_in(board, GIVER_PHONE)
    await set_location(board, viewer, BAKU)

    page = (
        await board.get(
            f"{PREFIX}/needs",
            params={"sort": "nearby", "radius_km": 50},
            headers=viewer,
        )
    ).json()
    assert [row["title"] for row in page["items"]] == ["Yaxın nərdivan"]


async def test_demand_is_a_count_and_not_a_list_of_people(board: AsyncClient) -> None:
    """ "Nərdivan - yaxınlıqda 2 nəfərə lazımdır" (Rule C, Rule F)."""
    admin = await sign_in(board, ADMIN_PHONE)
    for phone in (SEEKER_PHONE, THIRD_PHONE):
        person = await sign_in(board, phone)
        await board.patch(f"{PREFIX}/users/me", json={"full_name": "Nəfər"}, headers=person)
        await post_need(board, person, admin, title="Nərdivan", city=BAKU)

    demand = (await board.get(f"{PREFIX}/needs/demand")).json()
    ladder = next(row for row in demand if row["label"] == "Nərdivan")
    assert ladder["count"] == 2
    assert "user_id" not in ladder
    assert "Nəfər" not in (await board.get(f"{PREFIX}/needs/demand")).text


async def test_demand_groups_spellings_of_the_same_thing(board: AsyncClient) -> None:
    """Azerbaijani is routinely typed without diacritics, and a count split
    across two spellings of one word is a count that misleads."""
    admin = await sign_in(board, ADMIN_PHONE)
    first = await sign_in(board, SEEKER_PHONE)
    second = await sign_in(board, THIRD_PHONE)
    await post_need(board, first, admin, title="Nərdivan", city=BAKU)
    await post_need(board, second, admin, title="nerdivan", city=BAKU)

    demand = (await board.get(f"{PREFIX}/needs/demand")).json()
    assert len(demand) == 1
    assert demand[0]["count"] == 2


# ---------------------------------------------------------------------------
# Turning an unsuccessful request into demand (Rule C)
# ---------------------------------------------------------------------------
async def test_the_giver_chooses_and_the_rest_become_convertible(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin, city=BAKU)

    winner = await sign_in(board, SEEKER_PHONE)
    loser = await sign_in(board, THIRD_PHONE)
    await request_item(board, winner, int(listing["id"]))
    await request_item(board, loser, int(listing["id"]))

    # The public page says how many are waiting, never who.
    detail = (await board.get(f"{PREFIX}/products/{listing['slug']}")).json()
    assert detail["open_request_count"] == 2

    requesters = (
        await board.get(f"{PREFIX}/products/{listing['id']}/requesters", headers=giver)
    ).json()
    assert len(requesters) == 2

    chosen = requesters[0]["request_item_id"]
    handed = await board.post(
        f"{PREFIX}/products/{listing['id']}/handover",
        json={"request_item_id": chosen},
        headers=giver,
    )
    assert handed.status_code == 200
    assert len(handed.json()) == 1  # the person who was not selected

    # The loser is now offered the conversion; the winner is not.
    assert len((await board.get(f"{PREFIX}/needs/convertible", headers=loser)).json()) == 1
    assert (await board.get(f"{PREFIX}/needs/convertible", headers=winner)).json() == []


async def test_only_the_owner_sees_who_asked(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin)

    seeker = await sign_in(board, SEEKER_PHONE)
    await request_item(board, seeker, int(listing["id"]))

    # A 404, not a 403: the endpoint never confirms somebody else's id exists.
    assert (
        await board.get(f"{PREFIX}/products/{listing['id']}/requesters", headers=seeker)
    ).status_code == 404
    assert (
        await board.post(
            f"{PREFIX}/products/{listing['id']}/handover",
            json={"request_item_id": 1},
            headers=seeker,
        )
    ).status_code == 404


async def test_keeping_it_as_a_need_creates_one_and_only_one(board: AsyncClient) -> None:
    """The consent step, and its idempotence.

    The aggregate demand count is the product of this function; clicking
    twice must not make two people out of one.
    """
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin, city=BAKU)

    winner = await sign_in(board, SEEKER_PHONE)
    loser = await sign_in(board, THIRD_PHONE)
    await request_item(board, winner, int(listing["id"]))
    await request_item(board, loser, int(listing["id"]))

    requesters = (
        await board.get(f"{PREFIX}/products/{listing['id']}/requesters", headers=giver)
    ).json()
    winner_item = next(r for r in requesters if r["request_no"].endswith("0001"))
    await board.post(
        f"{PREFIX}/products/{listing['id']}/handover",
        json={"request_item_id": winner_item["request_item_id"]},
        headers=giver,
    )

    item_id = (await board.get(f"{PREFIX}/needs/convertible", headers=loser)).json()[0][
        "request_item_id"
    ]

    first = await board.post(f"{PREFIX}/needs/from-request-item/{item_id}", headers=loser)
    assert first.status_code == 201
    assert first.json()["title"] == "Nərdivan"
    # It inherits the listing's place, which is better evidence of where the
    # person can collect from than a profile they may never have filled in.
    assert first.json()["location"]["city"] == "Bakı"

    # The prompt stops being offered once it has been answered.
    assert (await board.get(f"{PREFIX}/needs/convertible", headers=loser)).json() == []
    assert len((await board.get(f"{PREFIX}/needs/mine", headers=loser)).json()) == 1


async def test_a_pending_request_cannot_be_converted(board: AsyncClient) -> None:
    """Converting before the giver has decided would pre-empt them."""
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin)

    seeker = await sign_in(board, SEEKER_PHONE)
    await request_item(board, seeker, int(listing["id"]))

    requesters = (
        await board.get(f"{PREFIX}/products/{listing['id']}/requesters", headers=giver)
    ).json()
    item_id = requesters[0]["request_item_id"]

    response = await board.post(f"{PREFIX}/needs/from-request-item/{item_id}", headers=seeker)
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "request_not_resolved"


async def test_you_cannot_convert_somebody_elses_request(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin)

    seeker = await sign_in(board, SEEKER_PHONE)
    await request_item(board, seeker, int(listing["id"]))
    item_id = (
        await board.get(f"{PREFIX}/products/{listing['id']}/requesters", headers=giver)
    ).json()[0]["request_item_id"]

    stranger = await sign_in(board, THIRD_PHONE)
    response = await board.post(f"{PREFIX}/needs/from-request-item/{item_id}", headers=stranger)
    assert response.status_code == 404


async def test_a_handed_over_giveaway_stops_being_available(board: AsyncClient) -> None:
    """A gift that has been given must stop inviting the next nine requests."""
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin)

    seeker = await sign_in(board, SEEKER_PHONE)
    await request_item(board, seeker, int(listing["id"]))
    item_id = (
        await board.get(f"{PREFIX}/products/{listing['id']}/requesters", headers=giver)
    ).json()[0]["request_item_id"]

    await board.post(
        f"{PREFIX}/products/{listing['id']}/handover",
        json={"request_item_id": item_id},
        headers=giver,
    )

    detail = (await board.get(f"{PREFIX}/products/{listing['slug']}")).json()
    assert detail["stock_status"] == "out_of_stock"
    assert detail["open_request_count"] == 0
