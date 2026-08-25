"""Category tree (plan.md 6.2)."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Response
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, Lang
from app.db.models import Category, Product
from app.schemas.catalogue import CategoryOut
from app.schemas.catalogue import Lang as LangLiteral

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", summary="Full two-level category tree")
async def list_categories(
    session: DbSession,
    lang: Lang,
    response: Response,
) -> list[CategoryOut]:
    """The whole tree in two queries, not one per node.

    `selectinload` on children is what keeps this at a fixed query count as
    the tree grows - a lazy relationship here would be a textbook N+1.
    """
    result = await session.execute(
        select(Category)
        .where(Category.parent_id.is_(None), Category.is_active.is_(True))
        # TWO levels, not one. CategoryOut.of recurses into each child and
        # reads child.children; with only one level loaded that is a lazy load,
        # which in async SQLAlchemy raises MissingGreenlet rather than quietly
        # issuing a query. The tree is capped at two levels (plan.md D11), so
        # this is the complete depth.
        .options(selectinload(Category.children).selectinload(Category.children))
        .order_by(Category.sort_order)
    )
    roots = list(result.scalars())

    # One grouped count for every category, rather than a count per node.
    counts_result = await session.execute(
        select(Product.category_id, func.count())
        .where(Product.public())
        .group_by(Product.category_id)
    )
    # tuple() per row: Row is a Sequence, not a 2-tuple, so dict() cannot
    # consume it directly and mypy is right to object.
    counts: dict[int, int] = {row[0]: row[1] for row in counts_result.all()}

    # A parent's count includes its children's, which is what a shopper expects
    # when they click a top-level category.
    for root in roots:
        counts[root.id] = counts.get(root.id, 0) + sum(
            counts.get(child.id, 0) for child in root.children
        )

    response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=300"
    return [CategoryOut.of(root, cast(LangLiteral, lang), counts) for root in roots]
