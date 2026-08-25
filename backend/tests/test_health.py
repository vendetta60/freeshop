"""Health probes and public config (plan.md phase 0 acceptance)."""

from __future__ import annotations

from httpx import AsyncClient

PREFIX = "/api/v1"


async def test_healthz_is_ok(client: AsyncClient) -> None:
    response = await client.get(f"{PREFIX}/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_readyz_reports_dependencies(client: AsyncClient) -> None:
    response = await client.get(f"{PREFIX}/readyz")
    body = response.json()
    assert response.status_code == 200, body
    assert body["checks"] == {"database": True, "uploads": True}


async def test_security_headers_present(client: AsyncClient) -> None:
    response = await client.get(f"{PREFIX}/healthz")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


async def test_public_config_reports_google_disabled(client: AsyncClient) -> None:
    """Credentials are not wired yet; the SPA must be told, not left guessing."""
    response = await client.get(f"{PREFIX}/meta/config")
    assert response.status_code == 200
    assert response.json()["google_enabled"] is False


async def test_unknown_route_uses_the_error_envelope(client: AsyncClient) -> None:
    response = await client.get(f"{PREFIX}/definitely-not-a-route")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["message"]  # localised, non-empty


async def test_error_message_is_localised(client: AsyncClient) -> None:
    az = await client.get(f"{PREFIX}/nope", headers={"Accept-Language": "az"})
    en = await client.get(f"{PREFIX}/nope", headers={"Accept-Language": "en"})
    assert az.json()["error"]["message"] == "Tapılmadı"
    assert en.json()["error"]["message"] == "Not found"
