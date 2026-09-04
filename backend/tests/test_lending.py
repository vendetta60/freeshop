"""Temporary lending (FreeShop_Prompt 7, Rule D).

A loan is not a gift with a note attached, so the lifecycle is tested as a
lifecycle: the happy path once, then every way of leaving the rails. The
transition table and the actor table are the two things that can go wrong,
and both are asserted from the outside rather than by reading the dicts.
"""

from __future__ import annotations

from httpx import AsyncClient

from tests.community import (
    ADMIN_PHONE,
    GIVER_PHONE,
    PREFIX,
    SEEKER_PHONE,
    THIRD_PHONE,
    board,
    offer,
    sign_in,
)

__all__ = ["board"]


async def _loan_listing(
    client: AsyncClient, giver: dict[str, str], admin: dict[str, str], **overrides: object
) -> dict[str, object]:
    payload: dict[str, object] = {"transfer_type": "loan", "max_borrow_days": 14}
    payload.update(overrides)
    return await offer(client, giver, admin, **payload)


async def _ask(
    client: AsyncClient, borrower: dict[str, str], product_id: int, **overrides: object
) -> dict[str, object]:
    payload: dict[str, object] = {"product_id": product_id, "requested_days": 7}
    payload.update(overrides)
    response = await client.post(f"{PREFIX}/loans", json=payload, headers=borrower)
    assert response.status_code == 201, response.text
    return dict(response.json())


async def _move(
    client: AsyncClient, headers: dict[str, str], loan_id: int, status: str
) -> AsyncClient | object:
    return await client.post(
        f"{PREFIX}/loans/{loan_id}/status", json={"status": status}, headers=headers
    )


# ---------------------------------------------------------------------------
# The listing side
# ---------------------------------------------------------------------------
async def test_existing_listings_are_giveaways(board: AsyncClient) -> None:
    """The back-fill value, asserted through the API.

    Every listing that predates lending is a give-away, and the default has
    to be the one that cannot turn a gift into a loan.
    """
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin)

    detail = (await board.get(f"{PREFIX}/products/{listing['slug']}")).json()
    assert detail["transfer_type"] == "giveaway"
    assert detail["loan_state"] == "available"


async def test_a_loan_listing_is_marked_and_filterable(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    await offer(board, giver, admin, title_az="Bağışlanan masa")
    await _loan_listing(board, giver, admin, title_az="Müvəqqəti nərdivan")

    loans = (await board.get(f"{PREFIX}/products", params={"transfer_type": "loan"})).json()
    assert [item["title"] for item in loans["items"]] == ["Müvəqqəti nərdivan"]
    assert loans["items"][0]["transfer_type"] == "loan"


async def test_you_cannot_ask_to_borrow_a_giveaway(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin)

    borrower = await sign_in(board, SEEKER_PHONE)
    response = await board.post(
        f"{PREFIX}/loans", json={"product_id": listing["id"]}, headers=borrower
    )
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "not_a_loan"


async def test_you_cannot_borrow_your_own_listing(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await _loan_listing(board, giver, admin)

    response = await board.post(
        f"{PREFIX}/loans", json={"product_id": listing["id"]}, headers=giver
    )
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "own_listing"


# ---------------------------------------------------------------------------
# The lifecycle
# ---------------------------------------------------------------------------
async def test_the_whole_lifecycle_request_to_return(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await _loan_listing(board, giver, admin)
    borrower = await sign_in(board, SEEKER_PHONE)

    loan = await _ask(board, borrower, int(listing["id"]))
    assert loan["status"] == "pending"

    approved = await _move(board, giver, int(loan["id"]), "approved")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    # Approving reserves the item and sets a return date.
    assert approved.json()["expected_return_at"] is not None

    reserved = (await board.get(f"{PREFIX}/products/{listing['slug']}")).json()
    assert reserved["loan_state"] == "reserved"

    borrowed = await _move(board, giver, int(loan["id"]), "borrowed")
    assert borrowed.json()["status"] == "borrowed"
    assert borrowed.json()["borrowed_at"] is not None
    assert (await board.get(f"{PREFIX}/products/{listing['slug']}")).json()[
        "loan_state"
    ] == "borrowed"

    returned = await _move(board, giver, int(loan["id"]), "returned")
    assert returned.json()["status"] == "returned"
    assert returned.json()["returned_at"] is not None
    # The listing is free again.
    assert (await board.get(f"{PREFIX}/products/{listing['slug']}")).json()[
        "loan_state"
    ] == "available"


async def test_approving_opens_the_conversation_the_parties_will_need(
    board: AsyncClient,
) -> None:
    """Approval is the moment two strangers have to arrange a doorstep."""
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await _loan_listing(board, giver, admin)
    borrower = await sign_in(board, SEEKER_PHONE)
    loan = await _ask(board, borrower, int(listing["id"]))

    assert (await board.get(f"{PREFIX}/conversations", headers=borrower)).json() == []
    await _move(board, giver, int(loan["id"]), "approved")

    threads = (await board.get(f"{PREFIX}/conversations", headers=borrower)).json()
    assert len(threads) == 1
    assert threads[0]["type"] == "loan"


async def test_only_one_borrower_can_hold_a_listing(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await _loan_listing(board, giver, admin)

    first = await _ask(board, await sign_in(board, SEEKER_PHONE), int(listing["id"]))
    second = await _ask(board, await sign_in(board, THIRD_PHONE), int(listing["id"]))

    assert (await _move(board, giver, int(first["id"]), "approved")).status_code == 200
    clash = await _move(board, giver, int(second["id"]), "approved")
    assert clash.status_code == 409
    assert clash.json()["error"]["details"]["reason"] == "already_lent"


async def test_asking_twice_while_the_first_ask_is_live_is_refused(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await _loan_listing(board, giver, admin)
    borrower = await sign_in(board, SEEKER_PHONE)

    await _ask(board, borrower, int(listing["id"]))
    again = await board.post(
        f"{PREFIX}/loans", json={"product_id": listing["id"]}, headers=borrower
    )
    assert again.status_code == 409
    assert again.json()["error"]["details"]["reason"] == "already_requested"


# ---------------------------------------------------------------------------
# Leaving the rails
# ---------------------------------------------------------------------------
async def test_a_loan_cannot_be_returned_before_it_is_collected(board: AsyncClient) -> None:
    """ "Returned" for an item that was never handed over is exactly the
    nonsense an explicit transition table exists to refuse."""
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await _loan_listing(board, giver, admin)
    borrower = await sign_in(board, SEEKER_PHONE)
    loan = await _ask(board, borrower, int(listing["id"]))

    response = await _move(board, giver, int(loan["id"]), "returned")
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "invalid_transition"
    assert response.json()["error"]["details"]["from"] == "pending"


async def test_a_terminal_loan_stays_terminal(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await _loan_listing(board, giver, admin)
    borrower = await sign_in(board, SEEKER_PHONE)
    loan = await _ask(board, borrower, int(listing["id"]))

    await _move(board, giver, int(loan["id"]), "rejected")
    for status in ("approved", "borrowed", "returned", "cancelled"):
        response = await _move(board, giver, int(loan["id"]), status)
        assert response.status_code == 409, status


async def test_the_borrower_cannot_approve_their_own_request(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await _loan_listing(board, giver, admin)
    borrower = await sign_in(board, SEEKER_PHONE)
    loan = await _ask(board, borrower, int(listing["id"]))

    response = await _move(board, borrower, int(loan["id"]), "approved")
    assert response.status_code == 403
    assert response.json()["error"]["details"]["reason"] == "wrong_party"


async def test_the_borrower_cannot_declare_it_returned(board: AsyncClient) -> None:
    """Only the owner confirms a return: they have to be holding the thing
    for it to be true."""
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await _loan_listing(board, giver, admin)
    borrower = await sign_in(board, SEEKER_PHONE)
    loan = await _ask(board, borrower, int(listing["id"]))
    await _move(board, giver, int(loan["id"]), "approved")
    await _move(board, giver, int(loan["id"]), "borrowed")

    assert (await _move(board, borrower, int(loan["id"]), "returned")).status_code == 403


async def test_either_party_may_cancel_before_the_handover(board: AsyncClient) -> None:
    """Forcing the borrower to ask the owner to cancel is how a request sits
    pending forever."""
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await _loan_listing(board, giver, admin)
    borrower = await sign_in(board, SEEKER_PHONE)
    loan = await _ask(board, borrower, int(listing["id"]))

    cancelled = await _move(board, borrower, int(loan["id"]), "cancelled")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


async def test_a_stranger_cannot_touch_a_loan(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await _loan_listing(board, giver, admin)
    borrower = await sign_in(board, SEEKER_PHONE)
    loan = await _ask(board, borrower, int(listing["id"]))

    stranger = await sign_in(board, THIRD_PHONE)
    # 404, not 403 - the endpoint never confirms the loan exists.
    assert (await board.get(f"{PREFIX}/loans/{loan['id']}", headers=stranger)).status_code == 404
    assert (await _move(board, stranger, int(loan["id"]), "approved")).status_code == 404


async def test_a_borrow_longer_than_the_owner_allows_is_refused(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await _loan_listing(board, giver, admin, max_borrow_days=3)
    borrower = await sign_in(board, SEEKER_PHONE)

    response = await board.post(
        f"{PREFIX}/loans",
        json={"product_id": listing["id"], "requested_days": 30},
        headers=borrower,
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"]["max"] == 3


# ---------------------------------------------------------------------------
# The two views of one row
# ---------------------------------------------------------------------------
async def test_the_same_loan_is_borrowed_to_one_party_and_lent_by_the_other(
    board: AsyncClient,
) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await _loan_listing(board, giver, admin)
    borrower = await sign_in(board, SEEKER_PHONE)
    await _ask(board, borrower, int(listing["id"]))

    mine = (await board.get(f"{PREFIX}/loans/mine", headers=borrower)).json()
    lent = (await board.get(f"{PREFIX}/loans/lent", headers=giver)).json()
    assert [row["role"] for row in mine] == ["borrower"]
    assert [row["role"] for row in lent] == ["owner"]
    assert mine[0]["id"] == lent[0]["id"]

    # And neither list contains the other person's phone number.
    assert GIVER_PHONE not in (await board.get(f"{PREFIX}/loans/mine", headers=borrower)).text
    assert SEEKER_PHONE not in (await board.get(f"{PREFIX}/loans/lent", headers=giver)).text
