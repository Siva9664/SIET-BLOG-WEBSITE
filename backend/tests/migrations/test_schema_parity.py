"""Schema-drift regression test: alembic history vs ORM metadata.

Fresh DB via ``alembic upgrade head`` ONLY, then diff Base.metadata
against the live schema. Fails on ANY missing table/column.
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.asyncio


def _candidate_urls() -> list[str]:
    # Every test must use only TEST_DATABASE_URL. Fall back to DATABASE_URL
    # here would risk running migrations/asserts against the real DB.
    # NOTE: the TEST_DATABASE_URL-vs-DATABASE_URL inequality guard lives in
    # tests/conftest.py; do not duplicate it here.
    test_url = os.environ.get("TEST_DATABASE_URL", "").strip()
    return [test_url] if test_url else []


def _is_safe_scratch_url(url: str) -> bool:
    lowered = url.lower()
    if "siet_db" in lowered and "siet_schema_check" not in lowered:
        return False
    return True


async def _wait_for_db(url: str, timeout_s: float = 5.0) -> bool:
    import asyncio

    try:
        engine = create_async_engine(url, poolclass=sa.pool.NullPool)
        async with engine.connect() as conn:
            await asyncio.wait_for(conn.execute(sa.text("SELECT 1")), timeout_s)
        await engine.dispose()
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def migrated_db_url():
    urls = [u for u in _candidate_urls() if _is_safe_scratch_url(u)]
    if not urls:
        pytest.skip("Set TEST_DATABASE_URL to scratch PG DB to run parity test.")
    url = urls[0]
    import asyncio
    import shutil

    async def _probe() -> bool:
        return await _wait_for_db(url)

    try:
        ok = asyncio.run(_probe())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            ok = loop.run_until_complete(_probe())
        finally:
            loop.close()
    if not ok:
        pytest.skip(f"Postgres unreachable at {url!r}.")
    backend_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    env = dict(os.environ, DATABASE_URL=url)
    alembic_bin = shutil.which("alembic") or os.path.join(
        os.path.dirname(sys.executable), "alembic"
    )
    if not os.path.exists(alembic_bin):
        alembic_bin = "alembic"
    subprocess.run(
        [alembic_bin, "downgrade", "base"],
        cwd=backend_dir, env=env, check=False,
        capture_output=True, text=True, timeout=300,
    )
    proc = subprocess.run(
        [alembic_bin, "upgrade", "head"],
        cwd=backend_dir, env=env, check=False,
        capture_output=True, text=True, timeout=600,
    )
    assert proc.returncode == 0, f"upgrade head failed:\n{proc.stdout}\n{proc.stderr}"
    proc2 = subprocess.run(
        [alembic_bin, "upgrade", "head"],
        cwd=backend_dir, env=env, check=False,
        capture_output=True, text=True, timeout=600,
    )
    assert proc2.returncode == 0, f"2nd upgrade head failed:\n{proc2.stdout}\n{proc2.stderr}"
    return url


async def test_alembic_head_matches_orm_metadata(migrated_db_url: str):
    from app.core.database import Base
    import app.modules.auth.models  # noqa: F401
    import app.modules.domains.models  # noqa: F401
    import app.modules.tags.models  # noqa: F401
    import app.modules.media.models  # noqa: F401
    import app.modules.news.models  # noqa: F401
    import app.modules.articles.models  # noqa: F401
    import app.modules.labs.models  # noqa: F401
    import app.modules.magazine.models  # noqa: F401
    import app.modules.engagement.models  # noqa: F401
    import app.modules.analytics.models  # noqa: F401
    import app.modules.documents.models  # noqa: F401
    import app.modules.template_engine.models  # noqa: F401
    import app.modules.settings.models  # noqa: F401

    engine = create_async_engine(migrated_db_url, poolclass=sa.pool.NullPool)
    try:
        async with engine.connect() as conn:
            def _inspect(sync_conn):
                insp = inspect(sync_conn)
                out: dict[str, set[str]] = {}
                for t in insp.get_table_names(schema="public"):
                    out[t] = {c["name"] for c in insp.get_columns(t, schema="public")}
                return out
            live = await conn.run_sync(_inspect)
    finally:
        await engine.dispose()

    missing_t: list[str] = []
    missing_c: list[str] = []
    for tname, table in Base.metadata.tables.items():
        if table.schema not in (None, "public"):
            continue
        if tname not in live:
            missing_t.append(tname)
            continue
        cols = live[tname]
        for col in table.columns:
            prop = getattr(getattr(col, "comparator", None), "property", None)
            if prop is not None and hasattr(prop, "mapper"):
                continue
            if col.name not in cols:
                missing_c.append(f"{tname}.{col.name}")
    errs: list[str] = []
    if missing_t:
        errs.append(f"missing tables: {sorted(missing_t)}")
    if missing_c:
        errs.append(f"missing columns: {sorted(missing_c)}")
    assert not errs, "Drift alembic vs ORM: " + "; ".join(errs)


async def test_magazine_insert_on_migrated_schema(migrated_db_url: str):
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from app.modules.magazine.models import Magazine, MagazinePage, MagazineTOCEntry

    engine = create_async_engine(migrated_db_url, poolclass=sa.pool.NullPool)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    slug = f"parity-{uuid.uuid4().hex[:8]}"
    try:
        async with maker() as session:
            mag = Magazine(title="Parity", slug=slug, publication_year=2026, status="draft")
            session.add(mag)
            await session.flush()
            session.add(MagazinePage(magazine_id=mag.id, page_number=1, image_url="http://x/p1.jpg"))
            session.add(MagazineTOCEntry(magazine_id=mag.id, page_number=1, heading="Intro"))
            await session.commit()
            pages = (await session.execute(select(MagazinePage).where(MagazinePage.magazine_id == mag.id))).scalars().all()
            toc = (await session.execute(select(MagazineTOCEntry).where(MagazineTOCEntry.magazine_id == mag.id))).scalars().all()
            assert len(pages) == 1
            assert len(toc) == 1
            for obj in list(pages) + list(toc) + [mag]:
                await session.delete(obj)
            await session.commit()
    finally:
        await engine.dispose()

