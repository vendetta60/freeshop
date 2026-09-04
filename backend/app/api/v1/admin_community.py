"""Admin routes for needs and emergency aid (FreeShop_Prompt 11, Rule E).

A SEPARATE MODULE, THE SAME ROUTER PREFIX. `api/v1/admin.py` is already 500
lines about the catalogue; bolting two more domains onto it would make the
one file every admin change touches. These routes mount under `/admin` and
carry the same `AdminUser` dependency, so from the outside they are one panel
(FreeShop_Prompt 11: "extend the existing admin panel rather than creating a
separate admin application").

This is the ONLY module in the application that can create an emergency aid
case, and the only one that serves `verification_note_internal`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import AdminUser, DbSession, Lang
from app.core.errors import NotFoundError, error_responses
from app.db.models import (
    AidCommitment,
    EmergencyAidCase,
    EmergencyAidItem,
    NeedRequest,
)
from app.schemas.catalogue import Page
from app.schemas.emergency import (
    AdminCaseOut,
    AdminCommitmentOut,
    AidItemIn,
    AidItemOut,
    AidItemUpdateIn,
    CaseIn,
    CaseStatusIn,
    CaseUpdateIn,
    CommitmentStatusIn,
)
from app.schemas.needs import AdminNeedOut, NeedModerationIn
from app.services import emergency_service, need_service

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    responses=error_responses(400, 401, 403, 404, 409, 422),
)

NO_STORE = {"Cache-Control": "no-store"}


# ---------------------------------------------------------------------------
# Needs moderation
# ---------------------------------------------------------------------------
@router.get("/needs", summary="Needs queue [admin]")
async def list_needs(
    admin: AdminUser,
    session: DbSession,
    lang: Lang,
    response: Response,
    status_filter: Annotated[
        str | None, Query(alias="status", description="pending|approved|rejected")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 25,
) -> Page[AdminNeedOut]:
    """The same shape and the same vocabulary as the product queue, so the
    panel can reuse its table, its filters and its status pills."""
    response.headers.update(NO_STORE)

    stmt = select(NeedRequest)
    if status_filter:
        stmt = stmt.where(NeedRequest.moderation_status == status_filter)

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

    rows = list(
        (
            await session.execute(
                stmt.options(*need_service.NEED_RELATIONS)
                # Oldest first while reviewing: a queue that shows the newest
                # first leaves the person who waited longest at the bottom.
                .order_by(
                    NeedRequest.created_at.asc()
                    if status_filter == "pending"
                    else NeedRequest.created_at.desc(),
                    NeedRequest.id.desc(),
                )
                .offset((page - 1) * per_page)
                .limit(per_page)
            )
        ).scalars()
    )

    return Page(
        items=[AdminNeedOut.of_admin(need, lang) for need in rows],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@router.post("/needs/{need_id}/moderate", summary="Approve or reject a need [admin]")
async def moderate_need(
    need_id: int,
    payload: NeedModerationIn,
    admin: AdminUser,
    session: DbSession,
    lang: Lang,
) -> AdminNeedOut:
    need = await need_service.load(session, need_id)
    updated = await need_service.moderate(session, need, status=payload.status, note=payload.note)
    await session.commit()
    return AdminNeedOut.of_admin(updated, lang)


# ---------------------------------------------------------------------------
# Emergency aid cases (Rule E - admin only, everywhere)
# ---------------------------------------------------------------------------
@router.get("/aid/cases", summary="All aid cases including drafts [admin]")
async def list_cases(
    admin: AdminUser, session: DbSession, lang: Lang, response: Response
) -> list[AdminCaseOut]:
    response.headers.update(NO_STORE)
    rows = await session.execute(
        select(EmergencyAidCase)
        .options(selectinload(EmergencyAidCase.items).selectinload(EmergencyAidItem.category))
        .order_by(EmergencyAidCase.created_at.desc())
    )
    return [AdminCaseOut.of_admin(case, lang) for case in rows.scalars()]


@router.get("/aid/cases/{case_id}", summary="One case, with internal notes [admin]")
async def get_case(
    case_id: int, admin: AdminUser, session: DbSession, lang: Lang, response: Response
) -> AdminCaseOut:
    response.headers.update(NO_STORE)
    return AdminCaseOut.of_admin(await emergency_service.load(session, case_id), lang)


@router.post(
    "/aid/cases",
    status_code=status.HTTP_201_CREATED,
    summary="Create an aid case as a draft [admin]",
)
async def create_case(
    payload: CaseIn, admin: AdminUser, session: DbSession, lang: Lang
) -> AdminCaseOut:
    """Created as a DRAFT, never published outright.

    Publishing is `POST /admin/aid/cases/{id}/status` with `active`. Two
    steps, because the first thing typed into a form about a house fire
    should not be the thing the whole town reads.
    """
    case = await emergency_service.create_case(session, payload.model_dump(), admin=admin)
    await session.commit()
    return AdminCaseOut.of_admin(case, lang)


@router.patch("/aid/cases/{case_id}", summary="Edit a case [admin]")
async def update_case(
    case_id: int, payload: CaseUpdateIn, admin: AdminUser, session: DbSession, lang: Lang
) -> AdminCaseOut:
    case = await emergency_service.load(session, case_id)
    updated = await emergency_service.update_case(
        session, case, payload.model_dump(exclude_unset=True)
    )
    await session.commit()
    return AdminCaseOut.of_admin(updated, lang)


@router.post("/aid/cases/{case_id}/status", summary="Publish, pause, complete or cancel [admin]")
async def set_case_status(
    case_id: int, payload: CaseStatusIn, admin: AdminUser, session: DbSession, lang: Lang
) -> AdminCaseOut:
    case = await emergency_service.load(session, case_id)
    updated = await emergency_service.set_case_status(session, case, payload.status)
    await session.commit()
    return AdminCaseOut.of_admin(updated, lang)


# ---------------------------------------------------------------------------
# Needed items
# ---------------------------------------------------------------------------
@router.post(
    "/aid/cases/{case_id}/items",
    status_code=status.HTTP_201_CREATED,
    summary="Add a needed item [admin]",
)
async def add_item(
    case_id: int, payload: AidItemIn, admin: AdminUser, session: DbSession, lang: Lang
) -> AidItemOut:
    case = await emergency_service.load(session, case_id)
    item = await emergency_service.add_item(session, case, payload.model_dump())
    await session.commit()
    return AidItemOut.of(item, lang)


@router.patch("/aid/items/{item_id}", summary="Edit a needed item [admin]")
async def update_item(
    item_id: int, payload: AidItemUpdateIn, admin: AdminUser, session: DbSession, lang: Lang
) -> AidItemOut:
    item = await emergency_service.load_item(session, item_id)
    updated = await emergency_service.update_item(
        session, item, payload.model_dump(exclude_unset=True)
    )
    await session.commit()
    return AidItemOut.of(updated, lang)


@router.delete(
    "/aid/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a needed item [admin]",
)
async def delete_item(item_id: int, admin: AdminUser, session: DbSession) -> None:
    """Hard delete, unusually for this codebase.

    An aid item is a line on a shopping list, not a record anybody's history
    depends on - and its commitments cascade with it, which is correct: an
    offer against a line that no longer exists is not an offer of anything.
    """
    item = await emergency_service.load_item(session, item_id)
    await session.delete(item)
    await session.commit()


# ---------------------------------------------------------------------------
# Community offers
# ---------------------------------------------------------------------------
@router.get("/aid/cases/{case_id}/commitments", summary="Offers against a case [admin]")
async def list_commitments(
    case_id: int, admin: AdminUser, session: DbSession, lang: Lang, response: Response
) -> list[AdminCommitmentOut]:
    """Who offered what, so the administrator can arrange the delivery.

    This is the only view in the application that names the offerers. It is
    behind `require_admin` because coordinating the handover is the job the
    administrator took on when they published the case.
    """
    response.headers.update(NO_STORE)
    rows = await session.execute(
        select(AidCommitment)
        .join(EmergencyAidItem, EmergencyAidItem.id == AidCommitment.item_id)
        .where(EmergencyAidItem.emergency_case_id == case_id)
        .options(
            selectinload(AidCommitment.user),
            selectinload(AidCommitment.item).selectinload(EmergencyAidItem.case),
        )
        .order_by(AidCommitment.created_at.desc())
    )
    return [AdminCommitmentOut.of_admin(commitment, lang) for commitment in rows.scalars()]


@router.post(
    "/aid/commitments/{commitment_id}/status",
    summary="Accept an offer, or mark it received [admin]",
)
async def set_commitment_status(
    commitment_id: int,
    payload: CommitmentStatusIn,
    admin: AdminUser,
    session: DbSession,
    lang: Lang,
) -> AdminCommitmentOut:
    """Marking `received` is what moves the public progress figure.

    It is an administrator's statement that the thing physically arrived, so
    it lives here and not on the offerer's route - a donor marking their own
    delivery received would make the page a wish list rather than a record.
    """
    commitment = (
        await session.execute(
            select(AidCommitment)
            .where(AidCommitment.id == commitment_id)
            .options(
                selectinload(AidCommitment.user),
                selectinload(AidCommitment.item).selectinload(EmergencyAidItem.case),
            )
        )
    ).scalar_one_or_none()
    if commitment is None:
        raise NotFoundError()

    updated = await emergency_service.set_commitment_status(
        session, commitment, status=payload.status, by_admin=True
    )
    await session.commit()
    return AdminCommitmentOut.of_admin(updated, lang)
