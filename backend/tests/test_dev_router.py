"""The dev router must be structurally unreachable outside development.

This is the test that backs the safety claim in plan.md 9.11 / 10: the OTP
inbox is not protected by a runtime check that could be bypassed, it is
simply never mounted.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.core import otp_inbox
from app.main import create_app
from tests.conftest import _test_settings

PREFIX = "/api/v1"


async def _client_for(settings: Settings) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=create_app(settings)),
        base_url="http://test",
    )


async def test_otp_inbox_available_in_development() -> None:
    async with await _client_for(_test_settings(env="development")) as client:
        response = await client.get(f"{PREFIX}/dev/otp-inbox")
        assert response.status_code == 200
        assert "items" in response.json()


@pytest.mark.parametrize("env", ["production", "test"])
async def test_otp_inbox_absent_outside_development(env: str) -> None:
    settings = _test_settings(
        env=env,
        jwt_secret="a-real-looking-secret-value-of-sufficient-length",
        otp_channel="telegram",  # console is refused in production
        demo_mode=False,  # the escape hatch must be off for this assertion
    )
    async with await _client_for(settings) as client:
        response = await client.get(f"{PREFIX}/dev/otp-inbox")
        assert response.status_code == 404


async def test_inbox_masks_phone_numbers_and_expires_entries() -> None:
    otp_inbox.clear()
    otp_inbox.record(
        phone="+994501234567",
        code="483920",
        purpose="login",
        channel="console",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    otp_inbox.record(
        phone="+994509999999",
        code="111111",
        purpose="login",
        channel="console",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),  # already expired
    )

    items = otp_inbox.recent()
    assert len(items) == 1, "expired entries must not be returned"
    assert items[0]["phone"] == "+99450***4567"
    assert "1234567" not in str(items[0])
    otp_inbox.clear()
