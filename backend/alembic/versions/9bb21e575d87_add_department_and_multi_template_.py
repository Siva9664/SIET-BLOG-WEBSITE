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
    """Upgrade schema."""
    # magazines table columns
    op.add_column('magazines', sa.Column('department_id', sa.Integer(), nullable=True))
    op.add_column('magazines', sa.Column('department_name', sa.String(length=150), nullable=True))
    op.add_column('magazines', sa.Column('target_page_budget', sa.Integer(), server_default='4', nullable=False))
    op.create_foreign_key('fk_magazines_department_id_domains', 'magazines', 'domains', ['department_id'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_magazines_department_id'), 'magazines', ['department_id'], unique=False)

    # magazine_templates table columns
    op.add_column('magazine_templates', sa.Column('department_id', sa.Integer(), nullable=True))
    op.add_column('magazine_templates', sa.Column('department_slug', sa.String(length=150), nullable=True))
    op.add_column('magazine_templates', sa.Column('template_family', sa.String(length=100), server_default='academic_digest', nullable=False))
    op.add_column('magazine_templates', sa.Column('page_budget', sa.Integer(), server_default='4', nullable=False))
    op.add_column('magazine_templates', sa.Column('description', sa.Text(), nullable=True))
    op.create_foreign_key('fk_magazine_templates_department_id_domains', 'magazine_templates', 'domains', ['department_id'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_magazine_templates_department_id'), 'magazine_templates', ['department_id'], unique=False)
    op.create_index(op.f('ix_magazine_templates_department_slug'), 'magazine_templates', ['department_slug'], unique=False)
    op.create_index(op.f('ix_magazine_templates_template_family'), 'magazine_templates', ['template_family'], unique=False)


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

