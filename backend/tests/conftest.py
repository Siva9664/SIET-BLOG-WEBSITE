import asyncio
import os
import random

import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# --- Test-database guard: refuse to run unless TEST_DATABASE_URL is set and
# differs from DATABASE_URL, and force every test to use only that DB. ---


def _norm_url(url: str) -> str:
    u = (url or "").strip()
    # Normalise driver prefixes so e.g. postgresql:// and postgresql+asyncpg://
    # pointing at the same DB compare equal.
    return (
        u.replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgres+asyncpg://", "postgres://")
        .rstrip("/")
    )


# Idempotent: `from tests.conftest import ...` re-executes this module *after*
# DATABASE_URL has already been overwritten with TEST_DATABASE_URL below, so a
# naive TEST_DATABASE_URL-vs-DATABASE_URL equality check would then fail
# spuriously. The env flag records that the guard already passed once; on
# re-import we only verify the binding is still consistent.
if os.environ.get("_SIET_TEST_DB_GUARD_DONE") == "1":
    _TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not _TEST_DB_URL:
        raise RuntimeError(
            "Refusing to run tests: TEST_DATABASE_URL is not set. "
            "Set TEST_DATABASE_URL to a scratch/test database URL."
        )
    _BOUND_CHECK_URL = os.environ.get("DATABASE_URL", "").strip()
    if _BOUND_CHECK_URL and _norm_url(_BOUND_CHECK_URL) != _norm_url(_TEST_DB_URL):
        raise RuntimeError(
            "Refusing to run tests: DATABASE_URL was changed after the test "
            f"DB guard passed (got {_BOUND_CHECK_URL!r})."
        )
else:
    _TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "").strip()
    _MAIN_DB_URL = os.environ.get("DATABASE_URL", "").strip()

    if not _TEST_DB_URL:
        raise RuntimeError(
            "Refusing to run tests: TEST_DATABASE_URL is not set. "
            "Set TEST_DATABASE_URL to a scratch/test database URL."
        )
    if _MAIN_DB_URL and _norm_url(_TEST_DB_URL) == _norm_url(_MAIN_DB_URL):
        raise RuntimeError(
            "Refusing to run tests: TEST_DATABASE_URL must differ from DATABASE_URL. "
            "Point TEST_DATABASE_URL at a dedicated scratch/test database."
        )

# Force the app settings / engine to bind to the test database only, before
# app modules are imported. This also covers the "DATABASE_URL-only" fallback:
# config DATABASE_URL defaults never leak into tests because settings reads
# this overridden value.
os.environ["DATABASE_URL"] = _TEST_DB_URL
# Mark the guard as passed so re-imports (e.g. `from tests.conftest import ...`
# after DATABASE_URL was overwritten) skip the one-time inequality check.
os.environ["_SIET_TEST_DB_GUARD_DONE"] = "1"

# Force testing environment configuration globally for test runs
os.environ["ENV"] = "testing"

from app.core.config import settings as _test_settings

_bound_db_url = str(_test_settings.DATABASE_URL or "")
if _norm_url(_bound_db_url) != _norm_url(_TEST_DB_URL):
    raise RuntimeError(
        "Refusing to run tests: app settings DATABASE_URL did not bind to "
        f"TEST_DATABASE_URL (got {_bound_db_url!r})."
    )

from app.main import app
from app.core.database import get_db, async_session_maker
from app.core.security import create_access_token, hash_password
from app.modules.auth.models import User

@pytest.fixture(scope="session")
def event_loop():
    """Create session-wide event loop for running async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides a transactional database session rolled back after test completion."""
    async with async_session_maker() as session:
        await session.begin()
        try:
            yield session
        finally:
            await session.rollback()

@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client yielding requests with overridden DB session injections."""
    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _create_user_and_token(db_session: AsyncSession, *, email_verified: bool, role: str = "user") -> str:
    user = User(
        name="Test User",
        email=f"fixture_{random.randint(100000, 999999)}@siet.in",
        password_hash=hash_password("Password123"),
        role=role,
        email_verified=email_verified,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return create_access_token(str(user.id), user.role)


@pytest_asyncio.fixture(scope="function")
async def admin_user(db_session: AsyncSession):
    """Persisted SUPER_ADMIN user for tests that need a real ``created_by_id``.

    Unlike a transient ``User(id=1, ...)`` stub, this row actually exists in
    the scratch DB, so ``Magazine.created_by_id`` FK constraints hold and the
    test never assumes the admin is user id 1.
    """
    from app.modules.auth.models import User, UserRole

    user = User(
        name="E2E Admin",
        email=f"e2e_admin_{random.randint(100000, 999999)}@siet.in",
        password_hash=hash_password("Password123"),
        role=UserRole.SUPER_ADMIN.value,
        is_active=True,
        is_verified=True,
        email_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def verified_user_token(db_session: AsyncSession) -> str:
    """Access token for a fresh, email-verified, non-admin user."""
    return await _create_user_and_token(db_session, email_verified=True)


@pytest_asyncio.fixture(scope="function")
async def unverified_user_token(db_session: AsyncSession) -> str:
    """Access token for a fresh, non-email-verified user."""
    return await _create_user_and_token(db_session, email_verified=False)
