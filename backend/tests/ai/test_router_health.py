"""Integration tests for admin /api/v1/magazine/ai/health endpoint authorization and diagnostics."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import _create_user_and_token


@pytest.mark.asyncio
async def test_magazine_ai_health_unauthorized(client: AsyncClient):
    """Verify unauthenticated request to /admin/magazine/ai/health is rejected with 401."""
    res = await client.get("/api/v1/admin/magazine/ai/health")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_magazine_ai_health_forbidden_for_regular_user(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Verify non-admin user request to /admin/magazine/ai/health is rejected with 403."""
    user_token = await _create_user_and_token(db_session, email_verified=True, role="user")
    res = await client.get(
        "/api/v1/admin/magazine/ai/health",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_magazine_ai_health_authorized_for_admin(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Verify admin user can access /admin/magazine/ai/health and receives diagnostic health payload."""
    admin_token = await _create_user_and_token(db_session, email_verified=True, role="super_admin")
    res = await client.get(
        "/api/v1/admin/magazine/ai/health",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    payload = data["data"]
    assert "status" in payload
    assert "configured_primary" in payload
    assert payload["configured_primary"] == "qwen"
    assert "primary" in payload
