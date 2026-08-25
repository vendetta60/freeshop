"""Declarative base and shared column mixins.

Every model inherits ``Base``. Models live in ``app/db/models/`` and are
imported here so Alembic autogenerate sees the full metadata (phase 3).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

# Explicit naming convention so Alembic emits stable, portable constraint
# names. Without this, autogenerate produces unnamed constraints that SQLite
# cannot drop and that differ from what PostgreSQL would create.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class UtcDateTime(TypeDecorator[datetime]):
    """Always-aware UTC timestamps.

    SQLite has no timestamp type: DateTime(timezone=True) writes a string and
    hands back a NAIVE datetime, so any comparison with datetime.now(UTC)
    raises "can't compare offset-naive and offset-aware datetimes". That is
    not a test artefact - it would break refresh-token and OTP expiry checks
    in production the same way.

    Binding rejects naive input outright rather than guessing a zone, because
    guessing is how timestamps silently drift by hours.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime written to a UtcDateTime column")
        return value.astimezone(UTC)

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        moment: datetime = value
        if moment.tzinfo is None:
            return moment.replace(tzinfo=UTC)
        return moment.astimezone(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def utcnow() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    """created_at / updated_at, always timezone-aware UTC."""

    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime,
        default=utcnow,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
        nullable=False,
    )
