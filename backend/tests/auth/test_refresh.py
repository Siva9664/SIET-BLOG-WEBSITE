import pytest
import random
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import hash_password
from app.modules.auth.models import User

@pytest.mark.asyncio
async def test_token_refresh(client: AsyncClient, db_session: AsyncSession):
    """Verify standard access token refresh lifecycle using refresh token."""
    email = f"testrefresh_{random.randint(1000, 9999)}@siet.in"
    password = "Password123"
    
    user = User(
        name="Refresh User",
        email=email,
        password_hash=hash_password(password),
        role="user",
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    login_payload = {
        "email": email,
        "password": password
    }
    res = await client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 200
    assert "refresh_token" not in res.json()
    assert "refresh_token" in res.cookies

    # The refresh token is httpOnly-cookie-only; the client's cookie jar carries it automatically.
    res = await client.post("/api/v1/auth/refresh")
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert res.json()["data"]["access_token"] is not None

