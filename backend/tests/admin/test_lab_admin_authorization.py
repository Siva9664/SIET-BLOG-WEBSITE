from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.modules.auth.models import User, UserRole
from app.modules.magazine.access import (
    check_magazine_access,
    check_template_access,
    resolve_creation_lab,
)
from app.modules.magazine.models import Magazine, MagazineTemplate
from app.shared.auth.dependencies import (
    check_object_lab_access,
    get_current_user,
    get_user_permitted_lab_ids,
    require_admin,
    require_lab_admin,
    require_super_admin,
    verify_user_lab_access,
)
from app.shared.exceptions.custom import ForbiddenException


# =============================================================================
# Helper Fixtures & Builders
# =============================================================================

def make_user(id: int, role: str, email: str = "test@siet.in") -> User:
    user = User(
        id=id,
        name=f"User {id}",
        email=email,
        role=role,
        is_active=True,
        is_verified=True,
    )
    return user


def make_mock_db(permitted_lab_ids: list[int] | None = None, template_assigned: bool = False):
    """Creates an AsyncSession mock with controlled scalar query results."""
    mock_db = AsyncMock()
    mock_result = MagicMock()

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = permitted_lab_ids if permitted_lab_ids is not None else []
    mock_scalars.first.return_value = MagicMock() if template_assigned else None

    mock_result.scalars.return_value = mock_scalars
    mock_db.execute.return_value = mock_result
    return mock_db


# =============================================================================
# 1. ROLE GUARD TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_require_super_admin():
    super_admin = make_user(1, UserRole.SUPER_ADMIN.value)
    lab_admin = make_user(2, UserRole.LAB_ADMIN.value)
    legacy_admin = make_user(3, UserRole.ADMIN.value)
    editor = make_user(4, UserRole.EDITOR.value)
    author = make_user(5, UserRole.AUTHOR.value)

    # Super Admin allowed
    res = await require_super_admin(current_user=super_admin)
    assert res == super_admin

    # All others forbidden
    for u in (lab_admin, legacy_admin, editor, author):
        with pytest.raises(ForbiddenException):
            await require_super_admin(current_user=u)


@pytest.mark.asyncio
async def test_require_lab_admin():
    super_admin = make_user(1, UserRole.SUPER_ADMIN.value)
    lab_admin = make_user(2, UserRole.LAB_ADMIN.value)
    legacy_admin = make_user(3, UserRole.ADMIN.value)
    editor = make_user(4, UserRole.EDITOR.value)
    author = make_user(5, UserRole.AUTHOR.value)

    # Super Admin, Lab Admin, Legacy ADMIN allowed
    assert (await require_lab_admin(current_user=super_admin)) == super_admin
    assert (await require_lab_admin(current_user=lab_admin)) == lab_admin
    assert (await require_lab_admin(current_user=legacy_admin)) == legacy_admin

    # require_admin alias works identically
    assert (await require_admin(current_user=super_admin)) == super_admin
    assert (await require_admin(current_user=lab_admin)) == lab_admin
    assert (await require_admin(current_user=legacy_admin)) == legacy_admin

    # Editor, Author strictly forbidden
    for u in (editor, author):
        with pytest.raises(ForbiddenException):
            await require_lab_admin(current_user=u)
        with pytest.raises(ForbiddenException):
            await require_admin(current_user=u)


# =============================================================================
# 2. LAB MEMBERSHIP & PERMITTED LAB IDS
# =============================================================================

@pytest.mark.asyncio
async def test_get_user_permitted_lab_ids():
    super_admin = make_user(1, UserRole.SUPER_ADMIN.value)
    lab_admin = make_user(2, UserRole.LAB_ADMIN.value)
    legacy_admin = make_user(3, UserRole.ADMIN.value)

    mock_db_super = make_mock_db(permitted_lab_ids=[1, 2, 3])
    mock_db_admin_a = make_mock_db(permitted_lab_ids=[1])
    mock_db_empty = make_mock_db(permitted_lab_ids=[])

    # Super admin queries active labs
    super_labs = await get_user_permitted_lab_ids(super_admin, mock_db_super)
    assert super_labs == [1, 2, 3]

    # Lab Admin A has Lab 1
    admin_labs = await get_user_permitted_lab_ids(lab_admin, mock_db_admin_a)
    assert admin_labs == [1]

    # Legacy Admin behaves identically to Lab Admin
    legacy_labs = await get_user_permitted_lab_ids(legacy_admin, mock_db_admin_a)
    assert legacy_labs == [1]

    # Admin with no active memberships
    no_labs = await get_user_permitted_lab_ids(lab_admin, mock_db_empty)
    assert no_labs == []


@pytest.mark.asyncio
async def test_verify_user_lab_access():
    super_admin = make_user(1, UserRole.SUPER_ADMIN.value)
    lab_admin_a = make_user(2, UserRole.LAB_ADMIN.value)
    author = make_user(4, UserRole.AUTHOR.value)

    mock_db = make_mock_db(permitted_lab_ids=[1])

    # Super Admin can access any lab without checking memberships
    assert await verify_user_lab_access(super_admin, lab_id=1, db=mock_db) is True
    assert await verify_user_lab_access(super_admin, lab_id=999, db=mock_db) is True

    # Lab Admin A can access Lab 1
    assert await verify_user_lab_access(lab_admin_a, lab_id=1, db=mock_db) is True

    # Lab Admin A CANNOT access Lab 2 (raises ForbiddenException)
    with pytest.raises(ForbiddenException):
        await verify_user_lab_access(lab_admin_a, lab_id=2, db=mock_db)

    # Author cannot access lab admin endpoints
    with pytest.raises(ForbiddenException):
        await verify_user_lab_access(author, lab_id=1, db=mock_db)


# =============================================================================
# 3. OBJECT-LEVEL LAB AUTHORIZATION & IDOR PREVENTION
# =============================================================================

@pytest.mark.asyncio
async def test_check_object_lab_access():
    super_admin = make_user(1, UserRole.SUPER_ADMIN.value)
    lab_admin_a = make_user(2, UserRole.LAB_ADMIN.value)

    mock_db = make_mock_db(permitted_lab_ids=[1])

    # Super Admin can access lab-scoped objects and global objects
    assert await check_object_lab_access(super_admin, object_lab_id=1, db=mock_db) is True
    assert await check_object_lab_access(super_admin, object_lab_id=2, db=mock_db) is True
    assert await check_object_lab_access(super_admin, object_lab_id=None, db=mock_db) is True

    # Lab Admin A can access Lab 1 objects
    assert await check_object_lab_access(lab_admin_a, object_lab_id=1, db=mock_db) is True

    # Lab Admin A CANNOT access Lab 2 objects (IDOR prevention)
    with pytest.raises(ForbiddenException):
        await check_object_lab_access(lab_admin_a, object_lab_id=2, db=mock_db)

    # Lab Admin A cannot access global objects unless explicitly allowed
    with pytest.raises(ForbiddenException):
        await check_object_lab_access(lab_admin_a, object_lab_id=None, db=mock_db, allow_global=False)

    # When allow_global=True, Lab Admin A can access global objects
    assert await check_object_lab_access(lab_admin_a, object_lab_id=None, db=mock_db, allow_global=True) is True


# =============================================================================
# 4. MAGAZINE AUTHORIZATION & IDOR PREVENTION
# =============================================================================

@pytest.mark.asyncio
async def test_check_magazine_access():
    super_admin = make_user(1, UserRole.SUPER_ADMIN.value)
    lab_admin_a = make_user(2, UserRole.LAB_ADMIN.value)
    lab_admin_b = make_user(3, UserRole.LAB_ADMIN.value)

    mock_db_a = make_mock_db(permitted_lab_ids=[1])
    mock_db_b = make_mock_db(permitted_lab_ids=[2])

    mag_a = Magazine(id=101, title="Lab A Magazine", lab_id=1)
    mag_b = Magazine(id=102, title="Lab B Magazine", lab_id=2)
    mag_unassigned = Magazine(id=103, title="Legacy Unassigned Magazine", lab_id=None)

    # Super Admin can access all magazines
    assert await check_magazine_access(super_admin, mag_a, mock_db_a) is True
    assert await check_magazine_access(super_admin, mag_b, mock_db_a) is True
    assert await check_magazine_access(super_admin, mag_unassigned, mock_db_a) is True

    # Lab Admin A can access mag_a
    assert await check_magazine_access(lab_admin_a, mag_a, mock_db_a) is True

    # Lab Admin A CANNOT access mag_b (IDOR prevention)
    with pytest.raises(ForbiddenException):
        await check_magazine_access(lab_admin_a, mag_b, mock_db_a)

    # Lab Admin A CANNOT access legacy unassigned magazine
    with pytest.raises(ForbiddenException):
        await check_magazine_access(lab_admin_a, mag_unassigned, mock_db_a)

    # Lab Admin B can access mag_b, but cannot access mag_a
    assert await check_magazine_access(lab_admin_b, mag_b, mock_db_b) is True
    with pytest.raises(ForbiddenException):
        await check_magazine_access(lab_admin_b, mag_a, mock_db_b)


# =============================================================================
# 5. TEMPLATE INHERITANCE & OWNERSHIP RULES (THE 3 RULES)
# =============================================================================

@pytest.mark.asyncio
async def test_check_template_access_rules():
    super_admin = make_user(1, UserRole.SUPER_ADMIN.value)
    lab_admin_a = make_user(2, UserRole.LAB_ADMIN.value)
    mock_db_a = make_mock_db(permitted_lab_ids=[1])

    tmpl_global = MagazineTemplate(id=201, name="Global Template", is_global=True, lab_id=None)
    tmpl_lab_a = MagazineTemplate(id=202, name="Lab A Template", is_global=False, lab_id=1)
    tmpl_lab_b = MagazineTemplate(id=203, name="Lab B Private Template", is_global=False, lab_id=2)
    tmpl_assigned = MagazineTemplate(id=204, name="Assigned Template", is_global=False, lab_id=99)

    # RULE 3: Global Template
    # Lab Admin A can read/use global template
    assert await check_template_access(lab_admin_a, tmpl_global, mock_db_a, require_write=False) is True
    # But Lab Admin A CANNOT edit/modify global template directly
    with pytest.raises(ForbiddenException):
        await check_template_access(lab_admin_a, tmpl_global, mock_db_a, require_write=True)

    # RULE 2: Lab-specific Template
    # Lab Admin A can read and write their own lab template
    assert await check_template_access(lab_admin_a, tmpl_lab_a, mock_db_a, require_write=False) is True
    assert await check_template_access(lab_admin_a, tmpl_lab_a, mock_db_a, require_write=True) is True

    # Cross-lab private template (Lab B) is completely blocked for Lab Admin A
    with pytest.raises(ForbiddenException):
        await check_template_access(lab_admin_a, tmpl_lab_b, mock_db_a, require_write=False)
    with pytest.raises(ForbiddenException):
        await check_template_access(lab_admin_a, tmpl_lab_b, mock_db_a, require_write=True)

    # RULE 1: Explicitly Assigned Template
    mock_db_assigned = make_mock_db(permitted_lab_ids=[1], template_assigned=True)
    assert await check_template_access(lab_admin_a, tmpl_assigned, mock_db_assigned, require_write=False) is True

    # SUPER ADMIN has full read & write access to ALL templates
    assert await check_template_access(super_admin, tmpl_global, mock_db_a, require_write=True) is True
    assert await check_template_access(super_admin, tmpl_lab_a, mock_db_a, require_write=True) is True
    assert await check_template_access(super_admin, tmpl_lab_b, mock_db_a, require_write=True) is True


# =============================================================================
# 6. CREATION LAB RESOLUTION
# =============================================================================

@pytest.mark.asyncio
async def test_resolve_creation_lab():
    super_admin = make_user(1, UserRole.SUPER_ADMIN.value)
    lab_admin = make_user(2, UserRole.LAB_ADMIN.value)

    # Super Admin can specify any lab or None
    assert await resolve_creation_lab(super_admin, requested_lab_id=None, db=AsyncMock()) is None
    assert await resolve_creation_lab(super_admin, requested_lab_id=42, db=AsyncMock()) == 42

    # Lab Admin with 1 lab auto-assigns
    mock_single_lab = make_mock_db(permitted_lab_ids=[10])
    assert await resolve_creation_lab(lab_admin, requested_lab_id=None, db=mock_single_lab) == 10
    assert await resolve_creation_lab(lab_admin, requested_lab_id=10, db=mock_single_lab) == 10

    # Lab Admin with 1 lab requesting another lab raises 403
    with pytest.raises(ForbiddenException):
        await resolve_creation_lab(lab_admin, requested_lab_id=99, db=mock_single_lab)

    # Lab Admin with multiple labs and none requested raises 400
    mock_multi_lab = make_mock_db(permitted_lab_ids=[10, 20])
    with pytest.raises(HTTPException) as exc_info:
        await resolve_creation_lab(lab_admin, requested_lab_id=None, db=mock_multi_lab)
    assert exc_info.value.status_code == 400

    # Lab Admin with no memberships raises 403
    mock_no_lab = make_mock_db(permitted_lab_ids=[])
    with pytest.raises(ForbiddenException):
        await resolve_creation_lab(lab_admin, requested_lab_id=None, db=mock_no_lab)


# =============================================================================
# 7. ROUTER LEVEL PERMISSION & INTEGRATION TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_router_level_authorization_matrix():
    super_admin = make_user(1, UserRole.SUPER_ADMIN.value)
    lab_admin = make_user(2, UserRole.LAB_ADMIN.value)
    author = make_user(3, UserRole.AUTHOR.value)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # A) Settings endpoint is restricted to SUPER_ADMIN only
        app.dependency_overrides[get_current_user] = lambda: lab_admin
        res = await client.get("/api/v1/admin/settings")
        assert res.status_code == 403

        # B) Media admin endpoint rejects AUTHOR
        app.dependency_overrides[get_current_user] = lambda: author
        res = await client.get("/api/v1/admin/media")
        assert res.status_code == 403

        # C) Magazine admin endpoint rejects AUTHOR
        res = await client.get("/api/v1/admin/magazine")
        assert res.status_code == 403

    app.dependency_overrides.clear()

