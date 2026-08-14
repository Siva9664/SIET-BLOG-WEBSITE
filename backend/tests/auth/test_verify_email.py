import pytest
import random
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import hash_password, create_access_token
from app.modules.auth.models import User

@pytest.mark.asyncio
async def test_user_email_verification_status(client: AsyncClient, db_session: AsyncSession):
    """Verify user profile reflects email_verified status."""
    email = f"testverify_{random.randint(1000, 9999)}@siet.in"
    user = User(
        name="Verify User",
        email=email,
        password_hash=hash_password("Password123"),
        role="user",
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    token = create_access_token(str(user.id), user.role)
    headers = {"Authorization": f"Bearer {token}"}
    res = await client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 200
    assert res.json()["is_verified"] is True


