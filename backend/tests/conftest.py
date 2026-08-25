"""Shared test fixtures.

Each test gets an app backed by a throwaway file database. A file rather than
:memory: because the app opens its own connections, and an in-memory SQLite
database is private per connection - the app would see an empty schema.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

# Importing the models is what registers them on `Base.metadata`. Without it
# `create_all` builds only the tables whose modules some OTHER test file
# happened to import first - so a file run on its own got a half-empty
# schema, and the same file passed as part of the full suite.
import app.db.models  # noqa: F401
from app.config import Settings, set_settings
from app.db.base import Base


def _test_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "env": "test",
        "database_url": "sqlite+aiosqlite:///:memory:",
        "jwt_secret": "test-secret-that-is-definitely-long-enough-32",
        "cors_origins": "http://localhost:5173",
        "google_client_id": "",
        "auth_phone_enabled": True,
        "otp_channel": "console",
        "demo_mode": False,
        # Pin the OTP limits to the plan.md 9.4 values. They are settings now,
        # so a developer who loosened them in .env for a shared demo would
        # otherwise silently turn the lockout tests into no-ops.
        "otp_max_sends_per_phone": 3,
        "otp_send_window_minutes": 15,
        "otp_max_sends_per_ip": 10,
        "otp_ip_window_minutes": 60,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stop a developer's real .env leaking into the suite."""
    for key in list(os.environ):
        if key.upper().startswith(
            ("JWT_", "GOOGLE_", "OTP_", "AUTH_", "DATABASE_", "DEMO_", "ENV")
        ):
            monkeypatch.delenv(key, raising=False)
    set_settings(None)


@pytest.fixture
async def db() -> AsyncIterator[tuple[AsyncEngine, async_sessionmaker, str]]:
    """A fresh schema per test."""
    path = Path(tempfile.mkdtemp()) / "test.db"
    url = f"sqlite+aiosqlite:///{path.as_posix()}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield engine, maker, url
    await engine.dispose()


def build_client(
    db_bundle: tuple[AsyncEngine, async_sessionmaker, str],
    monkeypatch: pytest.MonkeyPatch,
    **settings_overrides: object,
) -> AsyncClient:
    """Wire the application's session factory to the test database."""
    engine, maker, url = db_bundle
    import app.db.session as db_session

    monkeypatch.setattr(db_session, "engine", engine)
    monkeypatch.setattr(db_session, "SessionLocal", maker)

    from app.main import create_app

    app = create_app(_test_settings(env="development", database_url=url, **settings_overrides))
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def client(
    db: tuple[AsyncEngine, async_sessionmaker, str], monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncClient]:
    async with build_client(db, monkeypatch) as ac:
        yield ac
