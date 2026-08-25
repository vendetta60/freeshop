"""Async engine, SQLite pragmas, and the request-scoped session dependency.

The pragmas in ``_on_connect`` are what make SQLite viable for concurrent
reads under a web server (plan.md 8). WAL in particular lets readers proceed
while a write is in flight.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import BACKEND_ROOT, get_settings

_PRAGMAS: tuple[tuple[str, str], ...] = (
    ("journal_mode", "WAL"),  # readers never block on a writer
    ("synchronous", "NORMAL"),  # safe with WAL, far fewer fsyncs
    ("foreign_keys", "ON"),  # SQLite disables FK enforcement by default (!)
    ("busy_timeout", "5000"),  # wait rather than raise "database is locked"
    ("cache_size", "-64000"),  # 64 MB page cache
    ("temp_store", "MEMORY"),
)


def _ensure_sqlite_dir(url: str) -> None:
    """Create the directory for a file-backed SQLite DB before connecting."""
    marker = ":///"
    if "sqlite" not in url or marker not in url:
        return
    raw = url.split(marker, 1)[1]
    if not raw or raw == ":memory:":
        return
    path = Path(raw)
    if not path.is_absolute():
        path = BACKEND_ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)


def create_engine() -> AsyncEngine:
    settings = get_settings()
    _ensure_sqlite_dir(settings.database_url)

    engine = create_async_engine(
        settings.database_url,
        echo=False,
        future=True,
        pool_pre_ping=True,
    )

    if settings.database_url.startswith("sqlite"):

        @event.listens_for(engine.sync_engine, "connect")
        def _on_connect(dbapi_connection: Any, _record: Any) -> None:
            cursor = dbapi_connection.cursor()
            try:
                for name, value in _PRAGMAS:
                    cursor.execute(f"PRAGMA {name}={value};")
            finally:
                cursor.close()

    return engine


engine: AsyncEngine = create_engine()

SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a session that always closes."""
    async with SessionLocal() as session:
        yield session


async def ping() -> bool:
    """Cheap liveness probe for /readyz - does not touch application tables."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True


async def dispose_engine() -> None:
    await engine.dispose()
