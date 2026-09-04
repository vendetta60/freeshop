"""Public emergency aid endpoints (FreeShop_Prompt 8, Rule E, Rule F).

There is NO create route in this module. Publishing an official aid case is
an administrator's act, and the only routes that can do it live behind
`require_admin` in `api/v1/admin.py`. A public router that could create a
case would make Rule E a convention rather than a control.

The internal verification note has no path to this file either: every
response here is built from `CaseCardOut` / `CaseDetailOut`, neither of which
has the field (schemas/emergency.py).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, Lang, OptionalUser
from app.core.errors import NotFoundError, error_responses
from app.db.models import (
    CASE_PUBLIC_STATUSES,
    AidCommitment,
    EmergencyAidCase,
    EmergencyAidItem,
)
from app.schemas.emergency import (
    CaseCardOut,
    CaseDetailOut,
    CommitmentIn,
    CommitmentOut,
    CommitmentStatusIn,
)
from app.services import emergency_service, geo

router = APIRouter(
    prefix="/aid", tags=["emergency-aid"], responses=error_responses(401, 403, 404, 409, 422)
)


def _distance(origin: tuple[float, float] | None, case: EmergencyAidCase) -> float | None:
    """Rounded distance, or None when either side has no coordinates."""
    if origin is None or case.latitude is None or case.longitude is None:
        return None
    return geo.round_distance(geo.haversine_km(origin[0], origin[1], case.latitude, case.longitude))


@router.get("/cases", summary="Published aid cases")
async def list_cases(
    session: DbSession,
    lang: Lang,
    viewer: OptionalUser,
    active_only: Annotated[bool, Query(description="Hide completed cases")] = True,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[CaseCardOut]:
    """Active, paused and completed cases. Drafts are invisible.

    A completed case stays readable on purpose: closing the page the moment
    the family has what they need erases the record of a community that
    turned up, which is the opposite of what this feature is for.
    """
    statuses = ("active", "paused") if active_only else CASE_PUBLIC_STATUSES
    rows = await session.execute(
        select(EmergencyAidCase)
        .where(EmergencyAidCase.status.in_(statuses))
        .options(selectinload(EmergencyAidCase.items))
        .order_by(EmergencyAidCase.published_at.desc(), EmergencyAidCase.id.desc())
        .limit(limit)
    )
    cases = list(rows.scalars())

    origin = geo.origin_or_none(None, None, viewer)
    return [
        CaseCardOut.of(
            case,
            lang,
            distance_km=_distance(origin, case),
        )
        for case in cases
    ]


@router.get("/cases/{key}", summary="One case, by id or slug")
async def get_case(key: str, session: DbSession, lang: Lang, viewer: OptionalUser) -> CaseDetailOut:
    case = await emergency_service.load_public(session, key)
    origin = geo.origin_or_none(None, None, viewer)
    return CaseDetailOut.of_detail(case, lang, distance_km=_distance(origin, case))


# ---------------------------------------------------------------------------
# Offering help
# ---------------------------------------------------------------------------
@router.get("/commitments/mine", summary="What you have offered")
async def my_commitments(
    user: CurrentUser, session: DbSession, lang: Lang, response: Response
) -> list[CommitmentOut]:
    response.headers["Cache-Control"] = "no-store"
    return [
        CommitmentOut.of(commitment, lang)
        for commitment in await emergency_service.commitments_of(session, user.id)
    ]


@router.post(
    "/items/{item_id}/commitments",
    status_code=status.HTTP_201_CREATED,
    summary="Kömək edə bilərəm - offer to provide an item",
)
async def offer_help(
    item_id: int,
    payload: CommitmentIn,
    user: CurrentUser,
    session: DbSession,
    lang: Lang,
) -> CommitmentOut:
    """An offer, not a delivery.

    The item is not marked received here - an administrator confirms that
    when it actually arrives. Recording arrival on a click would tell the
    next visitor the family already has blankets that are still in somebody
    else's hallway (services/emergency_service).
    """
    item = await emergency_service.load_item(session, item_id)
    commitment = await emergency_service.offer(
        session, item, user=user, quantity=payload.quantity, note=payload.note
    )
    await session.commit()
    return CommitmentOut.of(commitment, lang)


@router.post("/commitments/{commitment_id}/status", summary="Withdraw your own offer")
async def cancel_commitment(
    commitment_id: int,
    payload: CommitmentStatusIn,
    user: CurrentUser,
    session: DbSession,
    lang: Lang,
) -> CommitmentOut:
    """Cancellation only.

    `accepted` and `received` are statements about what the family has been
    given, so they are the administrator's to make - the service refuses them
    here regardless of what is posted, and this route is scoped to the
    caller's own commitment on top of that.
    """
    commitment = (
        await session.execute(
            select(AidCommitment)
            # Scoped to the caller's own row, never by id alone (plan.md 10).
            .where(AidCommitment.id == commitment_id, AidCommitment.user_id == user.id)
            # Loaded through the item so the recount and the DTO have what
            # they need without a second round trip.
            .options(selectinload(AidCommitment.item).selectinload(EmergencyAidItem.case))
        )
    ).scalar_one_or_none()
    if commitment is None:
        raise NotFoundError()

    updated = await emergency_service.set_commitment_status(
        session, commitment, status=payload.status, by_admin=False
    )
    await session.commit()
    return CommitmentOut.of(updated, lang)
