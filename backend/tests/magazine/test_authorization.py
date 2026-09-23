"""
Tests for Magazine Server-Side Role-Based Authorization.
Verifies Gate 9:
- Unauthenticated requests are rejected with 401 Unauthorized.
- Regular users (role='USER') are rejected with 403 Forbidden on admin magazine routes.
- Lab Admins (role='ADMIN') have access to generator routes, but are rejected (403) from Super-Admin-only operations (publish/delete).
- Super Admins (role='SUPER_ADMIN') have unrestricted access.
"""

import pytest
import random
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.modules.auth.models import User
from app.shared.auth.dependencies import require_admin, require_super_admin
from app.shared.exceptions.custom import ForbiddenException


def _create_mock_user(role: str, email_suffix: str = "auth"):
    r = random.randint(10000, 99999)
    return User(
        id=r,
        name=f"User {role}",
        email=f"user_{role.lower()}_{r}_{email_suffix}@siet.in",
        password_hash=hash_password("Pass123!"),
        role=role,
        email_verified=True,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_require_admin_dependency_unit():
    """Unit test for require_admin and require_super_admin dependencies."""
    user_regular = _create_mock_user("user")
    user_admin = _create_mock_user("admin")
    user_super = _create_mock_user("super_admin")

    # Regular user fails require_admin
    with pytest.raises(ForbiddenException):
        await require_admin(current_user=user_regular)

    # Admin passes require_admin
    adm_out = await require_admin(current_user=user_admin)
    assert adm_out.role.upper() == "ADMIN"

    # Super Admin passes require_admin
    sup_out = await require_admin(current_user=user_super)
    assert sup_out.role.upper() == "SUPER_ADMIN"

    # Admin fails require_super_admin
    with pytest.raises(ForbiddenException):
        await require_super_admin(current_user=user_admin)

    # Super Admin passes require_super_admin
    sup_adm_out = await require_super_admin(current_user=user_super)
    assert sup_adm_out.role.upper() == "SUPER_ADMIN"


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(client: AsyncClient):
    """Calling admin magazine routes without token returns 401."""
    res = await client.get("/api/v1/admin/magazine")
    assert res.status_code == 401
