"""add_department_and_multi_template_support

Revision ID: 9bb21e575d87
Revises: 797e7d74a93d
Create Date: 2026-09-12 16:43:19.640453

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9bb21e575d87'
down_revision: Union[str, Sequence[str], None] = '797e7d74a93d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — idempotent: all columns use ADD COLUMN IF NOT EXISTS."""
    conn = op.get_bind()

    # magazines table columns
    conn.execute(sa.text("ALTER TABLE magazines ADD COLUMN IF NOT EXISTS department_id INTEGER REFERENCES domains(id) ON DELETE SET NULL"))
    conn.execute(sa.text("ALTER TABLE magazines ADD COLUMN IF NOT EXISTS department_name VARCHAR(150)"))
    conn.execute(sa.text("ALTER TABLE magazines ADD COLUMN IF NOT EXISTS target_page_budget INTEGER NOT NULL DEFAULT 4"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_magazines_department_id ON magazines(department_id)"))

    # magazine_templates table columns (may already exist from e4b4ce451d00)
    conn.execute(sa.text("ALTER TABLE magazine_templates ADD COLUMN IF NOT EXISTS department_id INTEGER REFERENCES domains(id) ON DELETE SET NULL"))
    conn.execute(sa.text("ALTER TABLE magazine_templates ADD COLUMN IF NOT EXISTS department_slug VARCHAR(150)"))
    conn.execute(sa.text("ALTER TABLE magazine_templates ADD COLUMN IF NOT EXISTS template_family VARCHAR(100) NOT NULL DEFAULT 'academic_digest'"))
    conn.execute(sa.text("ALTER TABLE magazine_templates ADD COLUMN IF NOT EXISTS page_budget INTEGER NOT NULL DEFAULT 4"))
    conn.execute(sa.text("ALTER TABLE magazine_templates ADD COLUMN IF NOT EXISTS description TEXT"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_magazine_templates_department_id   ON magazine_templates(department_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_magazine_templates_department_slug ON magazine_templates(department_slug)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_magazine_templates_template_family ON magazine_templates(template_family)"))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_magazine_templates_template_family'), table_name='magazine_templates')
    op.drop_index(op.f('ix_magazine_templates_department_slug'), table_name='magazine_templates')
    op.drop_index(op.f('ix_magazine_templates_department_id'), table_name='magazine_templates')
    op.drop_constraint('fk_magazine_templates_department_id_domains', 'magazine_templates', type_='foreignkey')
    op.drop_column('magazine_templates', 'description')
    op.drop_column('magazine_templates', 'page_budget')
    op.drop_column('magazine_templates', 'template_family')
    op.drop_column('magazine_templates', 'department_slug')
    op.drop_column('magazine_templates', 'department_id')

    op.drop_index(op.f('ix_magazines_department_id'), table_name='magazines')
    op.drop_constraint('fk_magazines_department_id_domains', 'magazines', type_='foreignkey')
    op.drop_column('magazines', 'target_page_budget')
    op.drop_column('magazines', 'department_name')
    op.drop_column('magazines', 'department_id')

