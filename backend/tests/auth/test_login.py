import pytest
import random
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import hash_password
from app.modules.auth.models import User

@pytest.mark.asyncio
async def test_login_success_and_me_retrieval(client: AsyncClient, db_session: AsyncSession):
    """Verify user login and profile retrieval using access token."""
    email = f"testlogin_{random.randint(1000, 9999)}@siet.in"
    password = "Password123"
    
    user = User(
        name="Login User",
        email=email,
        password_hash=hash_password(password),
        role="user",
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    login_payload = {
        "email": email,
        "password": password
    }
    res = await client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 200

    data = res.json()
    access_token = data["access_token"]
    assert access_token is not None
    assert data["user"]["email"] == email

    # Retrieve profile
    headers = {"Authorization": f"Bearer {access_token}"}
    res = await client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 200
    assert res.json()["email"] == email

@pytest.mark.asyncio
async def test_login_failure(client: AsyncClient):
    """Verify login fails with HTTP 401 on incorrect credentials."""
    login_payload = {
        "email": "nonexistent@siet.in",
        "password": "WrongPassword123"
    }
    res = await client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 401
    assert res.json()["success"] is False

