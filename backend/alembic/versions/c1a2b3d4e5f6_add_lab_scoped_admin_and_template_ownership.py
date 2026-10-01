"""add_lab_scoped_admin_and_template_ownership

Revision ID: c1a2b3d4e5f6
Revises: b1c2d3e4f5a6
Create Date: 2026-09-13 15:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c1a2b3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    def table_exists(name: str) -> bool:
        return conn.execute(
            sa.text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name=:n)"),
            {"n": name},
        ).scalar()

    def col_exists(tbl: str, col: str) -> bool:
        return conn.execute(
            sa.text("SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_schema='public' AND table_name=:t AND column_name=:c)"),
            {"t": tbl, "c": col},
        ).scalar()

    # 1. labs (may already exist from e4b4ce451d00)
    if not table_exists("labs"):
        conn.execute(sa.text("""
            CREATE TABLE labs (
                id           SERIAL PRIMARY KEY,
                name         VARCHAR(100) NOT NULL,
                code         VARCHAR(20),
                slug         VARCHAR(100),
                department_id INTEGER REFERENCES domains(id) ON DELETE SET NULL,
                description  TEXT,
                is_active    BOOLEAN NOT NULL DEFAULT TRUE,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                deleted_at   TIMESTAMPTZ,
                version      INTEGER NOT NULL DEFAULT 1
            )
        """))
    conn.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS ix_labs_slug ON labs(slug) WHERE slug IS NOT NULL"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_labs_id ON labs(id)"))

    # 2. lab_memberships
    if not table_exists("lab_memberships"):
        conn.execute(sa.text("""
            CREATE TABLE lab_memberships (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                lab_id     INTEGER NOT NULL REFERENCES labs(id) ON DELETE CASCADE,
                role       VARCHAR(20) NOT NULL DEFAULT 'LAB_ADMIN',
                is_active  BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                deleted_at TIMESTAMPTZ,
                version    INTEGER NOT NULL DEFAULT 1,
                CONSTRAINT uq_user_lab UNIQUE (user_id, lab_id)
            )
        """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_lab_memberships_user_id ON lab_memberships(user_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_lab_memberships_lab_id  ON lab_memberships(lab_id)"))

    # 3. template_lab_assignments (may already exist from e4b4ce451d00)
    if not table_exists("template_lab_assignments"):
        conn.execute(sa.text("""
            CREATE TABLE template_lab_assignments (
                id          SERIAL PRIMARY KEY,
                template_id INTEGER NOT NULL REFERENCES magazine_templates(id) ON DELETE CASCADE,
                lab_id      INTEGER NOT NULL REFERENCES labs(id) ON DELETE CASCADE,
                is_active   BOOLEAN NOT NULL DEFAULT TRUE,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                deleted_at  TIMESTAMPTZ,
                version     INTEGER NOT NULL DEFAULT 1,
                CONSTRAINT uq_template_lab UNIQUE (template_id, lab_id)
            )
        """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_template_lab_assignments_template_id ON template_lab_assignments(template_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_template_lab_assignments_lab_id      ON template_lab_assignments(lab_id)"))

    # 4. magazine_templates — add ownership columns
    conn.execute(sa.text("ALTER TABLE magazine_templates ADD COLUMN IF NOT EXISTS is_global BOOLEAN NOT NULL DEFAULT TRUE"))
    conn.execute(sa.text("ALTER TABLE magazine_templates ADD COLUMN IF NOT EXISTS lab_id INTEGER REFERENCES labs(id) ON DELETE SET NULL"))
    conn.execute(sa.text("ALTER TABLE magazine_templates ADD COLUMN IF NOT EXISTS priority INTEGER NOT NULL DEFAULT 0"))
    conn.execute(sa.text("ALTER TABLE magazine_templates ADD COLUMN IF NOT EXISTS created_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL"))
    conn.execute(sa.text("ALTER TABLE magazine_templates ADD COLUMN IF NOT EXISTS updated_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_magazine_templates_lab_id      ON magazine_templates(lab_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_magazine_templates_is_global   ON magazine_templates(is_global)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_magazine_templates_priority    ON magazine_templates(priority)"))

    # 5. magazines — add lab/template ownership columns
    conn.execute(sa.text("ALTER TABLE magazines ADD COLUMN IF NOT EXISTS lab_id INTEGER REFERENCES labs(id) ON DELETE SET NULL"))
    conn.execute(sa.text("ALTER TABLE magazines ADD COLUMN IF NOT EXISTS created_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL"))
    conn.execute(sa.text("ALTER TABLE magazines ADD COLUMN IF NOT EXISTS updated_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL"))
    conn.execute(sa.text("ALTER TABLE magazines ADD COLUMN IF NOT EXISTS template_id INTEGER REFERENCES magazine_templates(id) ON DELETE SET NULL"))
    conn.execute(sa.text("ALTER TABLE magazines ADD COLUMN IF NOT EXISTS template_version_id INTEGER"))
    conn.execute(sa.text("ALTER TABLE magazines ADD COLUMN IF NOT EXISTS review_notes TEXT"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_magazines_lab_id ON magazines(lab_id)"))

    # 6. media — add lab_id
    conn.execute(sa.text("ALTER TABLE media ADD COLUMN IF NOT EXISTS lab_id INTEGER REFERENCES labs(id) ON DELETE SET NULL"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_media_lab_id ON media(lab_id)"))

    # 7. source_documents — only if the table exists (it's not in the migration chain)
    if table_exists("source_documents"):
        conn.execute(sa.text("ALTER TABLE source_documents ADD COLUMN IF NOT EXISTS lab_id INTEGER REFERENCES labs(id) ON DELETE SET NULL"))
        conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_source_documents_lab_id ON source_documents(lab_id)"))

    # 8. template_versions — add snapshot/changelog columns (may already exist from e4b4ce451d00)
    if table_exists("template_versions"):
        conn.execute(sa.text("ALTER TABLE template_versions ADD COLUMN IF NOT EXISTS section_schema_snapshot JSONB"))
        conn.execute(sa.text("ALTER TABLE template_versions ADD COLUMN IF NOT EXISTS style_rules_snapshot JSONB"))
        conn.execute(sa.text("ALTER TABLE template_versions ADD COLUMN IF NOT EXISTS changelog TEXT"))
        conn.execute(sa.text("ALTER TABLE template_versions ADD COLUMN IF NOT EXISTS created_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL"))



def downgrade() -> None:
    # Reverse 8. template_versions
    op.drop_constraint('fk_template_versions_created_by_id', 'template_versions', type_='foreignkey')
    op.drop_column('template_versions', 'created_by_id')
    op.drop_column('template_versions', 'changelog')
    op.drop_column('template_versions', 'style_rules_snapshot')
    op.drop_column('template_versions', 'section_schema_snapshot')

    # Reverse 7. source_documents
    op.drop_index(op.f('ix_source_documents_lab_id'), table_name='source_documents')
    op.drop_constraint('fk_source_documents_lab_id', 'source_documents', type_='foreignkey')
    op.drop_column('source_documents', 'lab_id')

    # Reverse 6. media
    op.drop_index(op.f('ix_media_lab_id'), table_name='media')
    op.drop_constraint('fk_media_lab_id', 'media', type_='foreignkey')
    op.drop_column('media', 'lab_id')

    # Reverse 5. magazines
    op.drop_index(op.f('ix_magazines_lab_id'), table_name='magazines')
    op.drop_constraint('fk_magazines_template_version_id', 'magazines', type_='foreignkey')
    op.drop_constraint('fk_magazines_template_id', 'magazines', type_='foreignkey')
    op.drop_constraint('fk_magazines_updated_by_id', 'magazines', type_='foreignkey')
    op.drop_constraint('fk_magazines_created_by_id', 'magazines', type_='foreignkey')
    op.drop_constraint('fk_magazines_lab_id', 'magazines', type_='foreignkey')
    op.drop_column('magazines', 'review_notes')
    op.drop_column('magazines', 'template_version_id')
    op.drop_column('magazines', 'template_id')
    op.drop_column('magazines', 'updated_by_id')
    op.drop_column('magazines', 'created_by_id')
    op.drop_column('magazines', 'lab_id')

    # Reverse 4. magazine_templates
    op.drop_index(op.f('ix_magazine_templates_lab_id'), table_name='magazine_templates')
    op.drop_constraint('fk_magazine_templates_updated_by_id', 'magazine_templates', type_='foreignkey')
    op.drop_constraint('fk_magazine_templates_created_by_id', 'magazine_templates', type_='foreignkey')
    op.drop_constraint('fk_magazine_templates_lab_id', 'magazine_templates', type_='foreignkey')
    op.drop_column('magazine_templates', 'updated_by_id')
    op.drop_column('magazine_templates', 'created_by_id')
    op.drop_column('magazine_templates', 'priority')
    op.drop_column('magazine_templates', 'lab_id')
    op.drop_column('magazine_templates', 'is_global')

    # Reverse 3. template_lab_assignments
    op.drop_index(op.f('ix_template_lab_assignments_lab_id'), table_name='template_lab_assignments')
    op.drop_index(op.f('ix_template_lab_assignments_template_id'), table_name='template_lab_assignments')
    op.drop_index(op.f('ix_template_lab_assignments_id'), table_name='template_lab_assignments')
    op.drop_table('template_lab_assignments')

    # Reverse 2. lab_memberships
    op.drop_index(op.f('ix_lab_memberships_lab_id'), table_name='lab_memberships')
    op.drop_index(op.f('ix_lab_memberships_user_id'), table_name='lab_memberships')
    op.drop_index(op.f('ix_lab_memberships_id'), table_name='lab_memberships')
    op.drop_table('lab_memberships')

    # Reverse 1. labs
    op.drop_index(op.f('ix_labs_slug'), table_name='labs')
    op.drop_index(op.f('ix_labs_code'), table_name='labs')
    op.drop_index(op.f('ix_labs_id'), table_name='labs')
    op.drop_table('labs')
