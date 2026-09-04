"""Need DTOs (FreeShop_Prompt 4, 5, 6)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import NeedRequest
from app.schemas.location import LocationIn, LocationOut

NeedStatus = Literal["open", "partially_fulfilled", "fulfilled", "closed", "expired"]
NeedSort = Literal["newest", "nearby"]


class NeedIn(LocationIn):
    """Post a need.

    Inherits the location fields, so the same three lines describe where a
    listing is and where a need is - one shape for the frontend picker to
    fill, one resolver behind it (services/geo.py).
    """

    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, Field(min_length=2, max_length=200)]
    description: Annotated[str, Field(default="", max_length=4000)] = ""
    category_id: int | None = None
    quantity_needed: Annotated[int, Field(default=1, ge=1, le=999)] = 1


class NeedUpdateIn(LocationIn):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[str | None, Field(default=None, min_length=2, max_length=200)] = None
    description: Annotated[str | None, Field(default=None, max_length=4000)] = None
    category_id: int | None = None
    quantity_needed: Annotated[int | None, Field(default=None, ge=1, le=999)] = None


class NeedStatusIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: NeedStatus


class NeedModerationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["approved", "rejected"]
    note: Annotated[str | None, Field(default=None, max_length=500)] = None


class NeedCardOut(BaseModel):
    """A need as the board shows it.

    NO NAME, NO CONTACT. Who is looking for a pushchair is not public
    information (Rule F); a visitor who wants to help opens a conversation,
    which is an authorised, recorded, one-to-one act.
    """

    id: int
    title: str
    description: str
    category_id: int | None = None
    category_name: str | None = None
    quantity_needed: int
    status: NeedStatus
    location: LocationOut
    created_at: datetime

    @classmethod
    def of(
        cls, need: NeedRequest, lang: str = "az", *, distance_km: float | None = None
    ) -> NeedCardOut:
        return cls(
            id=need.id,
            title=need.title,
            description=need.description,
            category_id=need.category_id,
            category_name=need.category.name(lang) if need.category else None,
            quantity_needed=need.quantity_needed,
            status=need.status,
            location=LocationOut.of(need, distance_km),
            created_at=need.created_at,
        )


class MyNeedOut(NeedCardOut):
    """Your own need, with the moderation state you are entitled to see."""

    moderation_status: str
    moderation_note: str | None = None
    expires_at: datetime | None = None

    @classmethod
    def of_own(cls, need: NeedRequest, lang: str = "az") -> MyNeedOut:
        card = NeedCardOut.of(need, lang)
        return cls(
            **card.model_dump(),
            moderation_status=need.moderation_status,
            moderation_note=need.moderation_note,
            expires_at=need.expires_at,
        )


class AdminNeedOut(MyNeedOut):
    """The moderation queue row. Adds who posted it, which the queue needs
    and the public board must never have."""

    user_id: int
    user_label: str

    @classmethod
    def of_admin(cls, need: NeedRequest, lang: str = "az") -> AdminNeedOut:
        own = MyNeedOut.of_own(need, lang)
        user = need.user
        return cls(
            **own.model_dump(),
            user_id=need.user_id,
            user_label=user.full_name or user.phone or user.email or f"#{need.user_id}",
        )


class DemandOut(BaseModel):
    """Aggregated local demand - counts, never identities (Rule F).

    "Nərdivan - Yaxınlıqda 9 nəfərə lazımdır".
    """

    key: str
    label: str
    count: int
    category_id: int | None = None
    nearest_km: float | None = None


class NeedMatchOut(BaseModel):
    """A need shown to somebody who has the thing.

    The score is returned so the client can explain the ordering if it wants
    to; it is not secret, and hiding it would only make the ranking look
    arbitrary.
    """

    need: NeedCardOut
    score: float


class ConvertibleItemOut(BaseModel):
    """A listing request that went to someone else, offered back as a need.

    Drives "Bu əşyanı ala bilmədiniz. [Ehtiyac kimi saxla]" - the consent
    step that Rule C requires before demand becomes public.
    """

    request_item_id: int
    title: str
    product_id: int | None = None
    quantity: int
    decided_at: datetime | None = None
