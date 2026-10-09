"""Prepare the scratch TEST database (item 5 automation).

Runs, against TEST_DATABASE_URL only:
  1. ``alembic upgrade head`` (after an optional ``downgrade base`` reset),
  2. ``scripts/sync_db.py`` (legacy column safety net),
  3. ``scripts/check_admin.py`` (ensures admin@siet.ac.in exists).

Refuses to run when TEST_DATABASE_URL is unset, equals DATABASE_URL, or
does not look like a scratch DB. Tests themselves never assume the admin is
user id 1 (see the ``admin_user`` fixture in tests/conftest.py).
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys


def _run(cmd: list[str], cwd: str, env: dict[str, str], label: str) -> None:
    print(f"$ {' '.join(cmd)}  # {label}")
    proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if proc.stdout:
        print(proc.stdout[-4000:])
    if proc.returncode != 0:
        print(proc.stderr[-8000:], file=sys.stderr)
        raise SystemExit(f"{label} failed (exit {proc.returncode})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare the scratch TEST DB.")
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Skip the leading `alembic downgrade base` (default resets fresh).",
    )
    args = parser.parse_args()

    test_url = os.environ.get("TEST_DATABASE_URL", "").strip()
    main_url = os.environ.get("DATABASE_URL", "").strip()
    if not test_url:
        raise SystemExit("Refusing: TEST_DATABASE_URL is not set.")
    norm = lambda u: u.replace("postgresql+asyncpg://", "postgresql://").rstrip("/")
    if main_url and norm(test_url) == norm(main_url):
        raise SystemExit("Refusing: TEST_DATABASE_URL must differ from DATABASE_URL.")
    if "siet_db" in test_url.lower() and "siet_schema_check" not in test_url.lower():
        raise SystemExit(f"Refusing: {test_url!r} does not look like a scratch DB.")

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ, DATABASE_URL=test_url, PYTHONPATH=backend_dir)
    alembic_bin = shutil.which("alembic") or os.path.join(
        os.path.dirname(sys.executable), "alembic"
    )
    if not os.path.exists(alembic_bin):
        alembic_bin = "alembic"

    if not args.no_reset:
        subprocess.run(
            [alembic_bin, "downgrade", "base"],
            cwd=backend_dir, env=env, check=False,
            capture_output=True, text=True,
        )
    _run([alembic_bin, "upgrade", "head"], backend_dir, env, "alembic upgrade head")
    _run([sys.executable, "scripts/sync_db.py"], backend_dir, env, "sync_db.py")
    _run([sys.executable, "scripts/check_admin.py"], backend_dir, env, "check_admin.py")
    print(f"Scratch DB ready at {test_url}")


if __name__ == "__main__":
    main()
