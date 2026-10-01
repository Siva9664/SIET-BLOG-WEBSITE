"""add_example_outputs_to_magazine_templates

Revision ID: e4b4ce451d00
Revises: 2801f999c755
Create Date: 2026-08-31 09:14:54.509412

NOTE (2026-10-01): magazine_templates, labs, lab_memberships, template_lab_assignments,
      template_versions, template_pages, template_regions, magazine_pages,
      magazine_toc_entries were never created by any earlier migration (they were
      created directly on the legacy dev DB).  This migration creates them if
      missing using raw SQL so we avoid ordering issues with FKs.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e4b4ce451d00'
down_revision: Union[str, Sequence[str], None] = '2801f999c755'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, name: str) -> bool:
    return conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name=:n)"
        ),
        {"n": name},
    ).scalar()


def upgrade() -> None:
    """Upgrade schema — create any missing tables then add example_outputs."""
    conn = op.get_bind()

    # ── labs ──────────────────────────────────────────────────────────────────
    if not _table_exists(conn, "labs"):
        conn.execute(sa.text("""
            CREATE TABLE labs (
                id          SERIAL PRIMARY KEY,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                name        VARCHAR(255) NOT NULL,
                slug        VARCHAR(150),
                description TEXT,
                is_active   BOOLEAN NOT NULL DEFAULT TRUE,
                domain_id   INTEGER REFERENCES domains(id) ON DELETE SET NULL
            )
        """))
        conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_labs_slug ON labs(slug)"))
        conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_labs_is_active ON labs(is_active)"))

    # ── lab_memberships ───────────────────────────────────────────────────────
    if not _table_exists(conn, "lab_memberships"):
        conn.execute(sa.text("""
            CREATE TABLE lab_memberships (
                id          SERIAL PRIMARY KEY,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                lab_id      INTEGER NOT NULL REFERENCES labs(id) ON DELETE CASCADE,
                user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role        VARCHAR(50) NOT NULL DEFAULT 'member',
                is_active   BOOLEAN NOT NULL DEFAULT TRUE
            )
        """))

    # ── magazine_templates ────────────────────────────────────────────────────
    if not _table_exists(conn, "magazine_templates"):
        conn.execute(sa.text("""
            CREATE TABLE magazine_templates (
                id               SERIAL PRIMARY KEY,
                created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
                deleted_at       TIMESTAMPTZ,
                version          INTEGER NOT NULL DEFAULT 1,
                name             VARCHAR(255) NOT NULL DEFAULT 'SIET Standard Issue Template',
                department_id    INTEGER REFERENCES domains(id) ON DELETE SET NULL,
                department_slug  VARCHAR(150),
                template_family  VARCHAR(100) NOT NULL DEFAULT 'academic_digest',
                page_budget      INTEGER NOT NULL DEFAULT 4,
                description      TEXT,
                is_active        BOOLEAN NOT NULL DEFAULT TRUE,
                section_schema   JSON NOT NULL DEFAULT '[]',
                style_rules      JSON NOT NULL DEFAULT '{}',
                template_metadata JSON DEFAULT '{}',
                example_outputs  JSON DEFAULT '{}',
                is_global        BOOLEAN NOT NULL DEFAULT TRUE,
                lab_id           INTEGER REFERENCES labs(id) ON DELETE SET NULL,
                priority         INTEGER NOT NULL DEFAULT 0,
                created_by_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
                updated_by_id    INTEGER REFERENCES users(id) ON DELETE SET NULL
            )
        """))
        conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_magazine_templates_department_id    ON magazine_templates(department_id)"))
        conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_magazine_templates_department_slug  ON magazine_templates(department_slug)"))
        conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_magazine_templates_template_family  ON magazine_templates(template_family)"))
        conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_magazine_templates_is_active        ON magazine_templates(is_active)"))
        conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_magazine_templates_is_global        ON magazine_templates(is_global)"))
        conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_magazine_templates_lab_id           ON magazine_templates(lab_id)"))
        conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_magazine_templates_priority         ON magazine_templates(priority)"))
    else:
        # Table exists — just add the columns if missing.
        conn.execute(sa.text(
            "ALTER TABLE magazine_templates ADD COLUMN IF NOT EXISTS example_outputs JSON DEFAULT '{}'"
        ))
        conn.execute(sa.text("ALTER TABLE magazine_templates ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ"))
        conn.execute(sa.text("ALTER TABLE magazine_templates ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1"))

    # ── template_lab_assignments ───────────────────────────────────────────────
    if not _table_exists(conn, "template_lab_assignments"):
        conn.execute(sa.text("""
            CREATE TABLE template_lab_assignments (
                id          SERIAL PRIMARY KEY,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                template_id INTEGER NOT NULL REFERENCES magazine_templates(id) ON DELETE CASCADE,
                lab_id      INTEGER NOT NULL REFERENCES labs(id) ON DELETE CASCADE,
                is_active   BOOLEAN NOT NULL DEFAULT TRUE
            )
        """))

    # ── template_versions ─────────────────────────────────────────────────────
    if not _table_exists(conn, "template_versions"):
        conn.execute(sa.text("""
            CREATE TABLE template_versions (
                id                      SERIAL PRIMARY KEY,
                created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
                template_id             INTEGER NOT NULL REFERENCES magazine_templates(id) ON DELETE CASCADE,
                version_number          INTEGER NOT NULL DEFAULT 1,
                is_active               BOOLEAN NOT NULL DEFAULT TRUE,
                changelog               VARCHAR(255),
                section_schema_snapshot JSON,
                style_rules_snapshot    JSON,
                created_by_id           INTEGER REFERENCES users(id) ON DELETE SET NULL
            )
        """))
        conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_template_versions_template_id ON template_versions(template_id)"))

    # ── template_pages ────────────────────────────────────────────────────────
    if not _table_exists(conn, "template_pages"):
        conn.execute(sa.text("""
            CREATE TABLE template_pages (
                id            SERIAL PRIMARY KEY,
                created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
                version_id    INTEGER NOT NULL REFERENCES template_versions(id) ON DELETE CASCADE,
                page_number   INTEGER NOT NULL DEFAULT 1,
                width_pt      FLOAT NOT NULL DEFAULT 595.28,
                height_pt     FLOAT NOT NULL DEFAULT 841.89,
                margin_top    FLOAT NOT NULL DEFAULT 36.0,
                margin_bottom FLOAT NOT NULL DEFAULT 36.0,
                margin_left   FLOAT NOT NULL DEFAULT 36.0,
                margin_right  FLOAT NOT NULL DEFAULT 36.0
            )
        """))
        conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_template_pages_version_id ON template_pages(version_id)"))

    # ── template_regions ──────────────────────────────────────────────────────
    if not _table_exists(conn, "template_regions"):
        conn.execute(sa.text("""
            CREATE TABLE template_regions (
                id             SERIAL PRIMARY KEY,
                created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
                page_id        INTEGER NOT NULL REFERENCES template_pages(id) ON DELETE CASCADE,
                region_key     VARCHAR(100) NOT NULL,
                x_pt           FLOAT NOT NULL,
                y_pt           FLOAT NOT NULL,
                width_pt       FLOAT NOT NULL,
                height_pt      FLOAT NOT NULL,
                role           VARCHAR(50) NOT NULL DEFAULT 'feature',
                typography     JSON,
                color_palette  JSON
            )
        """))
        conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_template_regions_page_id ON template_regions(page_id)"))

    # ── template_embeddings ───────────────────────────────────────────────────
    if not _table_exists(conn, "template_embeddings"):
        conn.execute(sa.text("""
            CREATE TABLE template_embeddings (
                id              SERIAL PRIMARY KEY,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                template_id     INTEGER NOT NULL REFERENCES magazine_templates(id) ON DELETE CASCADE,
                section_type    VARCHAR(100) NOT NULL,
                example_key     VARCHAR(100) NOT NULL,
                content_text    TEXT NOT NULL,
                embedding       JSON,
                embedding_model VARCHAR(100) NOT NULL DEFAULT 'bge-base-en-v1.5'
            )
        """))
        conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_template_embeddings_template_id  ON template_embeddings(template_id)"))
        conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_template_embeddings_section_type ON template_embeddings(section_type)"))

    # ── magazine_pages ────────────────────────────────────────────────────────
    if not _table_exists(conn, "magazine_pages"):
        conn.execute(sa.text("""
            CREATE TABLE magazine_pages (
                id             SERIAL PRIMARY KEY,
                created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
                magazine_id    INTEGER NOT NULL REFERENCES magazines(id) ON DELETE CASCADE,
                page_number    INTEGER NOT NULL DEFAULT 1,
                image_url      TEXT,
                extracted_text TEXT
            )
        """))
        conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_magazine_pages_magazine_id ON magazine_pages(magazine_id)"))

    # ── magazine_toc_entries ──────────────────────────────────────────────────
    if not _table_exists(conn, "magazine_toc_entries"):
        conn.execute(sa.text("""
            CREATE TABLE magazine_toc_entries (
                id          SERIAL PRIMARY KEY,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                magazine_id INTEGER NOT NULL REFERENCES magazines(id) ON DELETE CASCADE,
                page_number INTEGER NOT NULL DEFAULT 1,
                heading     VARCHAR(255)
            )
        """))
        conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_magazine_toc_entries_magazine_id ON magazine_toc_entries(magazine_id)"))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE magazine_templates DROP COLUMN IF EXISTS example_outputs")
