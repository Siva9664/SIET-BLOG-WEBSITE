import pytest
import random
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import _create_user_and_token

@pytest.mark.asyncio
async def test_admin_user_creation(client: AsyncClient, db_session: AsyncSession):
    """Verify user creation via admin endpoint succeeds."""
    admin_token = await _create_user_and_token(db_session, email_verified=True, role="ADMIN")
    email = f"testregister_{random.randint(1000, 9999)}@siet.in"
    payload = {
        "name": "Register User",
        "email": email,
        "password": "Password123",
        "role": "user",
        "email_verified": True
    }
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = await client.post("/api/v1/admin/users", json=payload, headers=headers)
    assert res.status_code == 201
    assert res.json()["email"] == email

@pytest.mark.asyncio
async def test_admin_user_creation_duplicate_email(client: AsyncClient, db_session: AsyncSession):
    """Verify user creation returns 409 Conflict when email already exists."""
    admin_token = await _create_user_and_token(db_session, email_verified=True, role="ADMIN")
    email = f"testduplicate_{random.randint(1000, 9999)}@siet.in"
    payload = {
        "name": "Register User",
        "email": email,
        "password": "Password123",
        "role": "user",
        "email_verified": True
    }
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = await client.post("/api/v1/admin/users", json=payload, headers=headers)
    assert res.status_code == 201

    res = await client.post("/api/v1/admin/users", json=payload, headers=headers)
    assert res.status_code == 409

