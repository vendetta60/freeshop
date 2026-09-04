"""Conversations and messages (FreeShop_Prompt 3, 15).

The rule under test is one sentence: you may read a conversation if and only
if a participant row names you. Half of this file is that sentence attacked
from different directions - a stranger reading, a stranger writing, a
stranger marking read, a client trying to name its own recipient.

A thread you are not in returns 404 rather than 403 throughout, because
distinguishing "does not exist" from "not yours" would confirm that two named
people are talking to each other.
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
    post_need,
    sign_in,
)

__all__ = ["board"]


async def _thread_about(client: AsyncClient, headers: dict[str, str], listing_id: int) -> int:
    response = await client.post(
        f"{PREFIX}/conversations",
        json={"type": "listing", "context_id": listing_id},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


# ---------------------------------------------------------------------------
# Opening a thread
# ---------------------------------------------------------------------------
async def test_a_visitor_can_message_the_giver_of_a_listing(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin)

    seeker = await sign_in(board, SEEKER_PHONE)
    conversation_id = await _thread_about(board, seeker, int(listing["id"]))

    thread = (await board.get(f"{PREFIX}/conversations/{conversation_id}", headers=seeker)).json()
    assert thread["conversation"]["type"] == "listing"
    assert thread["conversation"]["subject"] == "Nərdivan"
    assert len(thread["conversation"]["participants"]) == 2


async def test_opening_the_same_thread_twice_reuses_it(board: AsyncClient) -> None:
    """A "Message" button that starts a new empty conversation on every click
    is how an inbox becomes unusable."""
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin)
    seeker = await sign_in(board, SEEKER_PHONE)

    first = await board.post(
        f"{PREFIX}/conversations",
        json={"type": "listing", "context_id": listing["id"]},
        headers=seeker,
    )
    second = await board.post(
        f"{PREFIX}/conversations",
        json={"type": "listing", "context_id": listing["id"]},
        headers=seeker,
    )
    assert first.status_code == 201
    # 200, not 201: nothing new was created, and a retrying client should know.
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


async def test_a_client_cannot_choose_who_it_reaches(board: AsyncClient) -> None:
    """The payload names a SUBJECT, never a recipient.

    `extra="forbid"` on the schema is what makes this a 422 rather than a
    silently ignored field - an API that accepted a `user_id` here would be
    an open channel to any account on the platform.
    """
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin)
    seeker = await sign_in(board, SEEKER_PHONE)

    response = await board.post(
        f"{PREFIX}/conversations",
        json={"type": "listing", "context_id": listing["id"], "user_id": 1},
        headers=seeker,
    )
    assert response.status_code == 422


async def test_you_cannot_open_a_thread_about_your_own_listing(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin)

    response = await board.post(
        f"{PREFIX}/conversations",
        json={"type": "listing", "context_id": listing["id"]},
        headers=giver,
    )
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "own_listing"


async def test_a_hidden_listing_cannot_be_used_to_open_a_thread(board: AsyncClient) -> None:
    """A pending listing is not public, so it cannot be a pretext for
    reaching the person who submitted it."""
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin, approve=False)

    seeker = await sign_in(board, SEEKER_PHONE)
    response = await board.post(
        f"{PREFIX}/conversations",
        json={"type": "listing", "context_id": listing["id"]},
        headers=seeker,
    )
    assert response.status_code == 404


async def test_a_need_can_be_answered_by_conversation(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    seeker = await sign_in(board, SEEKER_PHONE)
    need = await post_need(board, seeker, admin)

    helper = await sign_in(board, GIVER_PHONE)
    response = await board.post(
        f"{PREFIX}/conversations",
        json={"type": "need", "context_id": need["id"]},
        headers=helper,
    )
    assert response.status_code == 201
    assert response.json()["subject"] == "Nərdivan"


# ---------------------------------------------------------------------------
# Authorisation
# ---------------------------------------------------------------------------
async def test_a_stranger_cannot_read_a_conversation(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin)
    seeker = await sign_in(board, SEEKER_PHONE)
    conversation_id = await _thread_about(board, seeker, int(listing["id"]))
    await board.post(
        f"{PREFIX}/conversations/{conversation_id}/messages",
        json={"body": "Nərdivan hələ də var?"},
        headers=seeker,
    )

    stranger = await sign_in(board, THIRD_PHONE)
    read = await board.get(f"{PREFIX}/conversations/{conversation_id}", headers=stranger)
    assert read.status_code == 404
    assert "Nərdivan hələ də var?" not in read.text


async def test_a_stranger_cannot_write_into_a_conversation(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin)
    seeker = await sign_in(board, SEEKER_PHONE)
    conversation_id = await _thread_about(board, seeker, int(listing["id"]))

    stranger = await sign_in(board, THIRD_PHONE)
    for method, url in (
        ("post", f"{PREFIX}/conversations/{conversation_id}/messages"),
        ("post", f"{PREFIX}/conversations/{conversation_id}/read"),
    ):
        response = await getattr(board, method)(url, json={"body": "salam"}, headers=stranger)
        assert response.status_code == 404, url


async def test_a_signed_out_visitor_reaches_nothing(board: AsyncClient) -> None:
    assert (await board.get(f"{PREFIX}/conversations")).status_code == 401
    assert (await board.get(f"{PREFIX}/conversations/unread")).status_code == 401
    assert (await board.get(f"{PREFIX}/conversations/1")).status_code == 401


async def test_a_conversation_is_not_in_a_strangers_inbox(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin)
    seeker = await sign_in(board, SEEKER_PHONE)
    await _thread_about(board, seeker, int(listing["id"]))

    stranger = await sign_in(board, THIRD_PHONE)
    assert (await board.get(f"{PREFIX}/conversations", headers=stranger)).json() == []
    # Both parties do see it.
    assert len((await board.get(f"{PREFIX}/conversations", headers=seeker)).json()) == 1
    assert len((await board.get(f"{PREFIX}/conversations", headers=giver)).json()) == 1


# ---------------------------------------------------------------------------
# Messages and unread state
# ---------------------------------------------------------------------------
async def test_sending_and_reading_a_message(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin)
    seeker = await sign_in(board, SEEKER_PHONE)
    conversation_id = await _thread_about(board, seeker, int(listing["id"]))

    sent = await board.post(
        f"{PREFIX}/conversations/{conversation_id}/messages",
        json={"body": "Salam, nərdivan hələ də var?"},
        headers=seeker,
    )
    assert sent.status_code == 201

    thread = (await board.get(f"{PREFIX}/conversations/{conversation_id}", headers=giver)).json()
    assert [m["body"] for m in thread["messages"]] == ["Salam, nərdivan hələ də var?"]


async def test_unread_counts_the_other_persons_messages_only(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin)
    seeker = await sign_in(board, SEEKER_PHONE)
    conversation_id = await _thread_about(board, seeker, int(listing["id"]))

    await board.post(
        f"{PREFIX}/conversations/{conversation_id}/messages",
        json={"body": "Salam"},
        headers=seeker,
    )

    # The sender has nothing unread - showing them a badge for what they just
    # typed is the failure this guards.
    assert (await board.get(f"{PREFIX}/conversations/unread", headers=seeker)).json()[
        "conversations"
    ] == 0
    assert (await board.get(f"{PREFIX}/conversations/unread", headers=giver)).json()[
        "conversations"
    ] == 1

    # Reading the first page clears it.
    await board.get(f"{PREFIX}/conversations/{conversation_id}", headers=giver)
    assert (await board.get(f"{PREFIX}/conversations/unread", headers=giver)).json()[
        "conversations"
    ] == 0


async def test_an_empty_message_is_refused(board: AsyncClient) -> None:
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin)
    seeker = await sign_in(board, SEEKER_PHONE)
    conversation_id = await _thread_about(board, seeker, int(listing["id"]))

    for body in ("", "   "):
        response = await board.post(
            f"{PREFIX}/conversations/{conversation_id}/messages",
            json={"body": body},
            headers=seeker,
        )
        assert response.status_code == 422, body


async def test_a_thread_pages_backwards_from_the_newest(board: AsyncClient) -> None:
    """Keyset pagination on the id: a conversation being written to while it
    is read must not duplicate or skip a line."""
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin)
    seeker = await sign_in(board, SEEKER_PHONE)
    conversation_id = await _thread_about(board, seeker, int(listing["id"]))

    for index in range(5):
        await board.post(
            f"{PREFIX}/conversations/{conversation_id}/messages",
            json={"body": f"mesaj {index}"},
            headers=seeker,
        )

    first = (
        await board.get(
            f"{PREFIX}/conversations/{conversation_id}",
            params={"limit": 2},
            headers=seeker,
        )
    ).json()
    assert [m["body"] for m in first["messages"]] == ["mesaj 4", "mesaj 3"]
    assert first["next_before_id"] is not None

    second = (
        await board.get(
            f"{PREFIX}/conversations/{conversation_id}",
            params={"limit": 2, "before_id": first["next_before_id"]},
            headers=seeker,
        )
    ).json()
    assert [m["body"] for m in second["messages"]] == ["mesaj 2", "mesaj 1"]


async def test_paging_backwards_does_not_clear_the_badge(board: AsyncClient) -> None:
    """Reading history is not "I have seen the newest message"."""
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin)
    seeker = await sign_in(board, SEEKER_PHONE)
    conversation_id = await _thread_about(board, seeker, int(listing["id"]))

    for index in range(3):
        await board.post(
            f"{PREFIX}/conversations/{conversation_id}/messages",
            json={"body": f"mesaj {index}"},
            headers=seeker,
        )

    page = (
        await board.get(
            f"{PREFIX}/conversations/{conversation_id}", params={"limit": 1}, headers=giver
        )
    ).json()
    # First page: read.
    assert (await board.get(f"{PREFIX}/conversations/unread", headers=giver)).json()[
        "conversations"
    ] == 0

    # A second person writes, then the reader pages backwards.
    await board.post(
        f"{PREFIX}/conversations/{conversation_id}/messages",
        json={"body": "yeni mesaj"},
        headers=seeker,
    )
    await board.get(
        f"{PREFIX}/conversations/{conversation_id}",
        params={"before_id": page["next_before_id"]},
        headers=giver,
    )
    assert (await board.get(f"{PREFIX}/conversations/unread", headers=giver)).json()[
        "conversations"
    ] == 1


async def test_the_inbox_never_exposes_a_phone_number(board: AsyncClient) -> None:
    """Two people exchange whatever they choose to type; the platform does
    not hand over a phone number because somebody clicked a listing."""
    admin = await sign_in(board, ADMIN_PHONE)
    giver = await sign_in(board, GIVER_PHONE)
    listing = await offer(board, giver, admin)
    seeker = await sign_in(board, SEEKER_PHONE)
    conversation_id = await _thread_about(board, seeker, int(listing["id"]))

    body = (await board.get(f"{PREFIX}/conversations", headers=seeker)).text
    assert GIVER_PHONE not in body
    thread = (await board.get(f"{PREFIX}/conversations/{conversation_id}", headers=seeker)).text
    assert GIVER_PHONE not in thread
