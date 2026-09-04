"""Emergency aid DTOs (FreeShop_Prompt 8, 15).

THE ONE RULE THIS FILE ENFORCES: `verification_note_internal` appears on
`AdminCaseOut` and on no other model in this application. It records how a
family's misfortune was checked - who was telephoned, what was seen - and it
is written on the understanding that only the administrator reads it.

`AdminCaseOut` is returned exclusively by routes behind `require_admin`. The
public model is a separate class rather than the same class with a field
excluded, because an exclusion is one careless `model_dump()` away from
leaking and a missing field is not.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import AidCommitment, EmergencyAidCase, EmergencyAidItem
from app.schemas.location import LocationIn, LocationOut

CaseStatus = Literal["draft", "active", "paused", "completed", "cancelled"]
ItemPriority = Literal["urgent", "normal", "low"]
CommitmentStatus = Literal["offered", "accepted", "received", "cancelled"]


# ---------------------------------------------------------------------------
# Admin input
# ---------------------------------------------------------------------------
class CaseIn(LocationIn):
    model_config = ConfigDict(extra="forbid")

    title_az: Annotated[str, Field(min_length=2, max_length=200)]
    title_en: Annotated[str | None, Field(default=None, max_length=200)] = None
    description_az: Annotated[str, Field(default="", max_length=8000)] = ""
    description_en: Annotated[str | None, Field(default=None, max_length=8000)] = None
    beneficiary_display_name: Annotated[str | None, Field(default=None, max_length=120)] = None
    verification_note_internal: Annotated[str | None, Field(default=None, max_length=4000)] = None


class CaseUpdateIn(LocationIn):
    model_config = ConfigDict(extra="forbid")

    title_az: Annotated[str | None, Field(default=None, min_length=2, max_length=200)] = None
    title_en: Annotated[str | None, Field(default=None, max_length=200)] = None
    description_az: Annotated[str | None, Field(default=None, max_length=8000)] = None
    description_en: Annotated[str | None, Field(default=None, max_length=8000)] = None
    beneficiary_display_name: Annotated[str | None, Field(default=None, max_length=120)] = None
    verification_note_internal: Annotated[str | None, Field(default=None, max_length=4000)] = None


class CaseStatusIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: CaseStatus


class AidItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title_az: Annotated[str, Field(min_length=1, max_length=200)]
    title_en: Annotated[str | None, Field(default=None, max_length=200)] = None
    category_id: int | None = None
    quantity_needed: Annotated[int, Field(default=1, ge=1, le=999)] = 1
    priority: ItemPriority = "normal"
    notes: Annotated[str | None, Field(default=None, max_length=1000)] = None
    sort_order: int | None = None


class AidItemUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title_az: Annotated[str | None, Field(default=None, min_length=1, max_length=200)] = None
    title_en: Annotated[str | None, Field(default=None, max_length=200)] = None
    category_id: int | None = None
    quantity_needed: Annotated[int | None, Field(default=None, ge=1, le=999)] = None
    priority: ItemPriority | None = None
    notes: Annotated[str | None, Field(default=None, max_length=1000)] = None
    sort_order: int | None = None


class CommitmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantity: Annotated[int, Field(default=1, ge=1, le=999)] = 1
    note: Annotated[str | None, Field(default=None, max_length=1000)] = None


class CommitmentStatusIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: CommitmentStatus


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
class AidItemOut(BaseModel):
    id: int
    title: str
    category_id: int | None = None
    quantity_needed: int
    quantity_committed: int
    quantity_received: int
    priority: ItemPriority
    notes: str | None = None
    is_satisfied: bool

    @classmethod
    def of(cls, item: EmergencyAidItem, lang: str = "az") -> AidItemOut:
        return cls(
            id=item.id,
            title=item.title(lang),
            category_id=item.category_id,
            quantity_needed=item.quantity_needed,
            quantity_committed=item.quantity_committed,
            quantity_received=item.quantity_received,
            priority=item.priority,
            notes=item.notes,
            is_satisfied=item.is_satisfied,
        )


class CaseCardOut(BaseModel):
    """A case on the home page or the aid list. Public."""

    id: int
    slug: str
    title: str
    beneficiary_display_name: str | None = None
    status: CaseStatus
    location: LocationOut
    items_total: int
    items_satisfied: int
    published_at: datetime | None = None

    @classmethod
    def of(
        cls, case: EmergencyAidCase, lang: str = "az", *, distance_km: float | None = None
    ) -> CaseCardOut:
        return cls(
            id=case.id,
            slug=case.slug,
            title=case.title(lang),
            beneficiary_display_name=case.beneficiary_display_name,
            status=case.status,
            location=LocationOut.of(case, distance_km),
            items_total=len(case.items),
            items_satisfied=sum(1 for item in case.items if item.is_satisfied),
            published_at=case.published_at,
        )


class CaseDetailOut(CaseCardOut):
    """The public case page. NO internal verification note."""

    description: str
    items: list[AidItemOut]
    accepts_offers: bool

    @classmethod
    def of_detail(
        cls, case: EmergencyAidCase, lang: str = "az", *, distance_km: float | None = None
    ) -> CaseDetailOut:
        card = CaseCardOut.of(case, lang, distance_km=distance_km)
        return cls(
            **card.model_dump(),
            description=case.description(lang),
            items=[AidItemOut.of(item, lang) for item in case.items],
            accepts_offers=case.accepts_offers,
        )


class AdminCaseOut(CaseDetailOut):
    """ADMIN ONLY. The only model carrying the internal verification note."""

    verification_note_internal: str | None = None
    title_az: str
    title_en: str | None = None
    description_az: str
    description_en: str | None = None
    created_by_admin_id: int
    closed_at: datetime | None = None
    created_at: datetime

    @classmethod
    def of_admin(cls, case: EmergencyAidCase, lang: str = "az") -> AdminCaseOut:
        detail = CaseDetailOut.of_detail(case, lang)
        return cls(
            **detail.model_dump(),
            verification_note_internal=case.verification_note_internal,
            title_az=case.title_az,
            title_en=case.title_en,
            description_az=case.description_az,
            description_en=case.description_en,
            created_by_admin_id=case.created_by_admin_id,
            closed_at=case.closed_at,
            created_at=case.created_at,
        )


class CommitmentOut(BaseModel):
    id: int
    item_id: int
    item_title: str
    case_id: int
    case_title: str
    quantity: int
    status: CommitmentStatus
    note: str | None = None
    created_at: datetime

    @classmethod
    def of(cls, commitment: AidCommitment, lang: str = "az") -> CommitmentOut:
        item = commitment.item
        return cls(
            id=commitment.id,
            item_id=item.id,
            item_title=item.title(lang),
            case_id=item.emergency_case_id,
            case_title=item.case.title(lang),
            quantity=commitment.quantity,
            status=commitment.status,
            note=commitment.note,
            created_at=commitment.created_at,
        )


class AdminCommitmentOut(CommitmentOut):
    """Who offered, for the administrator arranging the delivery."""

    user_id: int
    user_label: str

    @classmethod
    def of_admin(cls, commitment: AidCommitment, lang: str = "az") -> AdminCommitmentOut:
        base = CommitmentOut.of(commitment, lang)
        user = commitment.user
        return cls(
            **base.model_dump(),
            user_id=commitment.user_id,
            user_label=user.full_name or user.phone or user.email or f"#{commitment.user_id}",
        )
