"""Matching, and admin-verified community aid (FreeShop_Prompt 6, 8).

Two features in one file because both are small and neither needs its own
fixture: matching is a pure ranking over rows the other suites already know
how to create, and the aid feature's whole surface is one admin flow plus one
public one.

The assertion that matters most here is
`test_the_internal_verification_note_never_reaches_the_public`: the field
records how a family's misfortune was checked, and it is the one piece of
data in this application with a hard admin-only promise attached.
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
    THIRD_PHONE,
    board,
    category_id,
    offer,
    post_need,
    sign_in,
)

__all__ = ["board"]


# ===========================================================================
# Matching (FreeShop_Prompt 6)
# ===========================================================================
async def test_a_listing_finds_the_needs_it_could_answer(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    seeker = await sign_in(board, SEEKER_PHONE)
    await post_need(board, seeker, admin, title="Nərdivan lazımdır", city=BAKU)

    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin, title_az="Nərdivan", city=BAKU)

    matches = (
        await board.get(f"{PREFIX}/products/{listing['id']}/matching-needs", headers=giver)
    ).json()
    assert len(matches) == 1
    assert matches[0]["need"]["title"] == "Nərdivan lazımdır"
    assert matches[0]["score"] > 0


async def test_matching_folds_diacritics(board: AsyncClient) -> None:
    """ "usaq arabasi" has to find "Uşaq arabası" - Azerbaijani is routinely
    typed without diacritics."""
    admin = await sign_in(board, ADMIN_PHONE)
    seeker = await sign_in(board, SEEKER_PHONE)
    await post_need(board, seeker, admin, title="usaq arabasi", city=BAKU)

    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin, title_az="Uşaq arabası", city=BAKU)

    matches = (
        await board.get(f"{PREFIX}/products/{listing['id']}/matching-needs", headers=giver)
    ).json()
    assert len(matches) == 1


async def test_a_need_too_far_away_is_not_a_match(board: AsyncClient) -> None:
    """A pushchair 200 km away is not a match, it is a road trip."""
    admin = await sign_in(board, ADMIN_PHONE)
    seeker = await sign_in(board, SEEKER_PHONE)
    await post_need(board, seeker, admin, title="Nərdivan", city=LANKARAN)

    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin, title_az="Nərdivan", city=BAKU)

    matches = (
        await board.get(
            f"{PREFIX}/products/{listing['id']}/matching-needs",
            params={"radius_km": 25},
            headers=giver,
        )
    ).json()
    assert matches == []


async def test_a_closed_need_is_never_matched(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    seeker = await sign_in(board, SEEKER_PHONE)
    need = await post_need(board, seeker, admin, title="Nərdivan", city=BAKU)
    await board.post(
        f"{PREFIX}/needs/{need['id']}/status", json={"status": "fulfilled"}, headers=seeker
    )

    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin, title_az="Nərdivan", city=BAKU)
    matches = (
        await board.get(f"{PREFIX}/products/{listing['id']}/matching-needs", headers=giver)
    ).json()
    assert matches == []


async def test_a_pending_need_is_never_matched(board: AsyncClient) -> None:
    """Matching must not be a way to read the moderation queue."""
    admin = await sign_in(board, ADMIN_PHONE)
    seeker = await sign_in(board, SEEKER_PHONE)
    await post_need(board, seeker, admin, title="Nərdivan", city=BAKU, approve=False)

    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin, title_az="Nərdivan", city=BAKU)
    matches = (
        await board.get(f"{PREFIX}/products/{listing['id']}/matching-needs", headers=giver)
    ).json()
    assert matches == []


async def test_your_own_need_is_not_offered_back_to_you(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    await post_need(board, giver, admin, title="Nərdivan", city=BAKU)
    listing = await offer(board, giver, admin, title_az="Nərdivan", city=BAKU)

    matches = (
        await board.get(f"{PREFIX}/products/{listing['id']}/matching-needs", headers=giver)
    ).json()
    assert matches == []


async def test_a_need_finds_the_listings_that_could_answer_it(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    await offer(board, giver, admin, title_az="Nərdivan", city=BAKU)
    await offer(board, giver, admin, title_az="Yemək masası", city=BAKU)

    seeker = await sign_in(board, SEEKER_PHONE)
    need = await post_need(board, seeker, admin, title="Nərdivan", city=BAKU)

    matches = (await board.get(f"{PREFIX}/needs/{need['id']}/matching-listings")).json()
    assert [row["title"] for row in matches] == ["Nərdivan"]


async def test_matching_needs_is_not_open_to_anonymous_callers(board: AsyncClient) -> None:
    """The needs are public one at a time; a list of who wants what, keyed to
    a listing, is the aggregation Rule F asks us not to hand to strangers."""
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin)
    assert (await board.get(f"{PREFIX}/products/{listing['id']}/matching-needs")).status_code == 401


# ===========================================================================
# Emergency aid (FreeShop_Prompt 8, Rule E)
# ===========================================================================
async def _case(
    client: AsyncClient, admin: dict[str, str], **overrides: object
) -> dict[str, object]:
    payload: dict[str, object] = {
        "title_az": "Lənkəranda yanğın",
        "description_az": "Evini itirmiş ailəyə yardım lazımdır.",
        "beneficiary_display_name": "Lənkəranda bir ailə",
        "verification_note_internal": "Rayon icra hakimiyyəti ilə danışıldı, akt görüldü.",
        "city": LANKARAN,
    }
    payload.update(overrides)
    response = await client.post(f"{PREFIX}/admin/aid/cases", json=payload, headers=admin)
    assert response.status_code == 201, response.text
    return dict(response.json())


async def _item(
    client: AsyncClient, admin: dict[str, str], case_id: int, **overrides: object
) -> dict[str, object]:
    payload: dict[str, object] = {"title_az": "Yorğan", "quantity_needed": 2}
    payload.update(overrides)
    response = await client.post(
        f"{PREFIX}/admin/aid/cases/{case_id}/items", json=payload, headers=admin
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


async def test_only_an_admin_can_create_an_official_case(board: AsyncClient) -> None:
    """Rule E. A badge reading "Təcili yardım" is a claim about somebody's
    life; a board where anyone can apply it to their own post is a board
    where it stops meaning anything."""
    ordinary = await sign_in(board, SEEKER_PHONE)
    response = await board.post(
        f"{PREFIX}/admin/aid/cases", json={"title_az": "Mənə yardım lazımdır"}, headers=ordinary
    )
    assert response.status_code == 403

    # And there is no public route that could do it either.
    assert (await board.post(f"{PREFIX}/aid/cases", json={"title_az": "x"})).status_code == 405


async def test_a_new_case_is_a_draft_and_invisible(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    case = await _case(board, admin)
    assert case["status"] == "draft"

    assert (await board.get(f"{PREFIX}/aid/cases")).json() == []
    # Guessing the id or the slug reaches nothing.
    assert (await board.get(f"{PREFIX}/aid/cases/{case['id']}")).status_code == 404
    assert (await board.get(f"{PREFIX}/aid/cases/{case['slug']}")).status_code == 404


async def test_publishing_puts_the_case_in_front_of_the_community(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    case = await _case(board, admin)
    await _item(board, admin, int(case["id"]))

    published = await board.post(
        f"{PREFIX}/admin/aid/cases/{case['id']}/status", json={"status": "active"}, headers=admin
    )
    assert published.status_code == 200
    assert published.json()["published_at"] is not None

    public = (await board.get(f"{PREFIX}/aid/cases")).json()
    assert [row["id"] for row in public] == [case["id"]]

    detail = (await board.get(f"{PREFIX}/aid/cases/{case['slug']}")).json()
    assert detail["title"] == "Lənkəranda yanğın"
    assert detail["beneficiary_display_name"] == "Lənkəranda bir ailə"
    assert detail["location"]["label"] == "Lənkəran"
    assert [item["title"] for item in detail["items"]] == ["Yorğan"]


async def test_the_internal_verification_note_never_reaches_the_public(
    board: AsyncClient,
) -> None:
    """The one hard admin-only promise in this application.

    Asserted over the whole response body rather than one field, so a note
    surfacing through any nested DTO later trips this test.
    """
    admin = await sign_in(board, ADMIN_PHONE)
    case = await _case(board, admin)
    await board.post(
        f"{PREFIX}/admin/aid/cases/{case['id']}/status", json={"status": "active"}, headers=admin
    )

    secret = "Rayon icra hakimiyyəti"
    ordinary = await sign_in(board, SEEKER_PHONE)
    for headers in ({}, ordinary):
        for url in (f"{PREFIX}/aid/cases", f"{PREFIX}/aid/cases/{case['slug']}"):
            body = (await board.get(url, headers=headers)).text
            assert secret not in body, url
            assert "verification_note_internal" not in body, url

    # The administrator does see it - that is what it is for.
    assert secret in (await board.get(f"{PREFIX}/admin/aid/cases/{case['id']}", headers=admin)).text
    # ...and an ordinary account cannot reach the admin view.
    assert (
        await board.get(f"{PREFIX}/admin/aid/cases/{case['id']}", headers=ordinary)
    ).status_code == 403


async def test_a_community_member_offers_and_the_admin_confirms_delivery(
    board: AsyncClient,
) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    case = await _case(board, admin)
    item = await _item(board, admin, int(case["id"]))
    await board.post(
        f"{PREFIX}/admin/aid/cases/{case['id']}/status", json={"status": "active"}, headers=admin
    )

    helper = await sign_in(board, GIVER_PHONE)
    offered = await board.post(
        f"{PREFIX}/aid/items/{item['id']}/commitments",
        json={"quantity": 2, "note": "Sabah gətirə bilərəm."},
        headers=helper,
    )
    assert offered.status_code == 201
    assert offered.json()["status"] == "offered"

    # An offer is not a delivery: the item is promised, not received.
    detail = (await board.get(f"{PREFIX}/aid/cases/{case['slug']}")).json()
    assert detail["items"][0]["quantity_committed"] == 2
    assert detail["items"][0]["quantity_received"] == 0
    assert detail["items"][0]["is_satisfied"] is False

    commitment_id = offered.json()["id"]
    await board.post(
        f"{PREFIX}/admin/aid/commitments/{commitment_id}/status",
        json={"status": "accepted"},
        headers=admin,
    )
    received = await board.post(
        f"{PREFIX}/admin/aid/commitments/{commitment_id}/status",
        json={"status": "received"},
        headers=admin,
    )
    assert received.status_code == 200

    settled = (await board.get(f"{PREFIX}/aid/cases/{case['slug']}")).json()
    assert settled["items"][0]["quantity_received"] == 2
    assert settled["items"][0]["is_satisfied"] is True
    assert settled["items_satisfied"] == 1


async def test_a_donor_cannot_mark_their_own_delivery_received(board: AsyncClient) -> None:
    """A donor confirming their own delivery would turn the public page into
    a wish list."""
    admin = await sign_in(board, ADMIN_PHONE)
    case = await _case(board, admin)
    item = await _item(board, admin, int(case["id"]))
    await board.post(
        f"{PREFIX}/admin/aid/cases/{case['id']}/status", json={"status": "active"}, headers=admin
    )

    helper = await sign_in(board, GIVER_PHONE)
    commitment = (
        await board.post(
            f"{PREFIX}/aid/items/{item['id']}/commitments", json={"quantity": 1}, headers=helper
        )
    ).json()

    response = await board.post(
        f"{PREFIX}/aid/commitments/{commitment['id']}/status",
        json={"status": "accepted"},
        headers=helper,
    )
    assert response.status_code == 403


async def test_a_donor_may_always_withdraw(board: AsyncClient) -> None:
    """An offer that cannot be withdrawn is one people hesitate to make."""
    admin = await sign_in(board, ADMIN_PHONE)
    case = await _case(board, admin)
    item = await _item(board, admin, int(case["id"]))
    await board.post(
        f"{PREFIX}/admin/aid/cases/{case['id']}/status", json={"status": "active"}, headers=admin
    )

    helper = await sign_in(board, GIVER_PHONE)
    commitment = (
        await board.post(
            f"{PREFIX}/aid/items/{item['id']}/commitments", json={"quantity": 2}, headers=helper
        )
    ).json()

    withdrawn = await board.post(
        f"{PREFIX}/aid/commitments/{commitment['id']}/status",
        json={"status": "cancelled"},
        headers=helper,
    )
    assert withdrawn.status_code == 200
    # A cancelled offer counts for nothing, which is the point of cancelling.
    detail = (await board.get(f"{PREFIX}/aid/cases/{case['slug']}")).json()
    assert detail["items"][0]["quantity_committed"] == 0


async def test_you_cannot_withdraw_somebody_elses_offer(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    case = await _case(board, admin)
    item = await _item(board, admin, int(case["id"]))
    await board.post(
        f"{PREFIX}/admin/aid/cases/{case['id']}/status", json={"status": "active"}, headers=admin
    )

    helper = await sign_in(board, GIVER_PHONE)
    commitment = (
        await board.post(
            f"{PREFIX}/aid/items/{item['id']}/commitments", json={"quantity": 1}, headers=helper
        )
    ).json()

    stranger = await sign_in(board, THIRD_PHONE)
    response = await board.post(
        f"{PREFIX}/aid/commitments/{commitment['id']}/status",
        json={"status": "cancelled"},
        headers=stranger,
    )
    assert response.status_code == 404


async def test_a_paused_case_is_readable_but_closed_to_offers(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    case = await _case(board, admin)
    item = await _item(board, admin, int(case["id"]))
    await board.post(
        f"{PREFIX}/admin/aid/cases/{case['id']}/status", json={"status": "active"}, headers=admin
    )
    await board.post(
        f"{PREFIX}/admin/aid/cases/{case['id']}/status", json={"status": "paused"}, headers=admin
    )

    detail = (await board.get(f"{PREFIX}/aid/cases/{case['slug']}")).json()
    assert detail["status"] == "paused"
    assert detail["accepts_offers"] is False

    helper = await sign_in(board, GIVER_PHONE)
    refused = await board.post(
        f"{PREFIX}/aid/items/{item['id']}/commitments", json={"quantity": 1}, headers=helper
    )
    assert refused.status_code == 409
    assert refused.json()["error"]["details"]["reason"] == "case_not_active"


async def test_a_completed_case_cannot_be_reopened(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    case = await _case(board, admin)
    await board.post(
        f"{PREFIX}/admin/aid/cases/{case['id']}/status", json={"status": "active"}, headers=admin
    )
    await board.post(
        f"{PREFIX}/admin/aid/cases/{case['id']}/status",
        json={"status": "completed"},
        headers=admin,
    )

    response = await board.post(
        f"{PREFIX}/admin/aid/cases/{case['id']}/status", json={"status": "active"}, headers=admin
    )
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "invalid_transition"


async def test_offering_help_opens_a_line_to_the_coordinator(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    case = await _case(board, admin)
    item = await _item(board, admin, int(case["id"]))
    await board.post(
        f"{PREFIX}/admin/aid/cases/{case['id']}/status", json={"status": "active"}, headers=admin
    )

    helper = await sign_in(board, GIVER_PHONE)
    await board.post(
        f"{PREFIX}/aid/items/{item['id']}/commitments", json={"quantity": 1}, headers=helper
    )

    threads = (await board.get(f"{PREFIX}/conversations", headers=helper)).json()
    assert len(threads) == 1
    assert threads[0]["type"] == "emergency"


async def test_the_admin_sees_who_offered_and_the_public_does_not(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    case = await _case(board, admin)
    item = await _item(board, admin, int(case["id"]))
    await board.post(
        f"{PREFIX}/admin/aid/cases/{case['id']}/status", json={"status": "active"}, headers=admin
    )

    helper = await sign_in(board, GIVER_PHONE)
    await board.patch(f"{PREFIX}/users/me", json={"full_name": "Kamran Əliyev"}, headers=helper)
    await board.post(
        f"{PREFIX}/aid/items/{item['id']}/commitments", json={"quantity": 1}, headers=helper
    )

    assert "Kamran" not in (await board.get(f"{PREFIX}/aid/cases/{case['slug']}")).text
    offers = (
        await board.get(f"{PREFIX}/admin/aid/cases/{case['id']}/commitments", headers=admin)
    ).json()
    assert offers[0]["user_label"] == "Kamran Əliyev"


async def test_an_aid_item_can_carry_a_category(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    case = await _case(board, admin)
    item = await _item(board, admin, int(case["id"]), category_id=await category_id(board, admin))
    assert item["category_id"] is not None
