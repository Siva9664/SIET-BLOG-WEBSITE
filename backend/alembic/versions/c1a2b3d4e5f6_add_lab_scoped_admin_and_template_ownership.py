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
    # 1. Create labs table
    op.create_table(
        'labs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('department_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_labs_id'), 'labs', ['id'], unique=False)
    op.create_index(op.f('ix_labs_code'), 'labs', ['code'], unique=True)
    op.create_index(op.f('ix_labs_slug'), 'labs', ['slug'], unique=True)

    # 2. Create lab_memberships table
    op.create_table(
        'lab_memberships',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('lab_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), server_default='LAB_ADMIN', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.ForeignKeyConstraint(['lab_id'], ['labs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'lab_id', name='uq_user_lab')
    )
    op.create_index(op.f('ix_lab_memberships_id'), 'lab_memberships', ['id'], unique=False)
    op.create_index(op.f('ix_lab_memberships_user_id'), 'lab_memberships', ['user_id'], unique=False)
    op.create_index(op.f('ix_lab_memberships_lab_id'), 'lab_memberships', ['lab_id'], unique=False)

    # 3. Create template_lab_assignments table
    op.create_table(
        'template_lab_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=False),
        sa.Column('lab_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.ForeignKeyConstraint(['lab_id'], ['labs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['template_id'], ['magazine_templates.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('template_id', 'lab_id', name='uq_template_lab')
    )
    op.create_index(op.f('ix_template_lab_assignments_id'), 'template_lab_assignments', ['id'], unique=False)
    op.create_index(op.f('ix_template_lab_assignments_template_id'), 'template_lab_assignments', ['template_id'], unique=False)
    op.create_index(op.f('ix_template_lab_assignments_lab_id'), 'template_lab_assignments', ['lab_id'], unique=False)

    # 4. Add columns to magazine_templates
    op.add_column('magazine_templates', sa.Column('is_global', sa.Boolean(), server_default=sa.text('true'), nullable=False))
    op.add_column('magazine_templates', sa.Column('lab_id', sa.Integer(), nullable=True))
    op.add_column('magazine_templates', sa.Column('priority', sa.Integer(), server_default=sa.text('0'), nullable=False))
    op.add_column('magazine_templates', sa.Column('created_by_id', sa.Integer(), nullable=True))
    op.add_column('magazine_templates', sa.Column('updated_by_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_magazine_templates_lab_id', 'magazine_templates', 'labs', ['lab_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_magazine_templates_created_by_id', 'magazine_templates', 'users', ['created_by_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_magazine_templates_updated_by_id', 'magazine_templates', 'users', ['updated_by_id'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_magazine_templates_lab_id'), 'magazine_templates', ['lab_id'], unique=False)

    # 5. Add columns to magazines
    op.add_column('magazines', sa.Column('lab_id', sa.Integer(), nullable=True))
    op.add_column('magazines', sa.Column('created_by_id', sa.Integer(), nullable=True))
    op.add_column('magazines', sa.Column('updated_by_id', sa.Integer(), nullable=True))
    op.add_column('magazines', sa.Column('template_id', sa.Integer(), nullable=True))
    op.add_column('magazines', sa.Column('template_version_id', sa.Integer(), nullable=True))
    op.add_column('magazines', sa.Column('review_notes', sa.Text(), nullable=True))
    op.create_foreign_key('fk_magazines_lab_id', 'magazines', 'labs', ['lab_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_magazines_created_by_id', 'magazines', 'users', ['created_by_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_magazines_updated_by_id', 'magazines', 'users', ['updated_by_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_magazines_template_id', 'magazines', 'magazine_templates', ['template_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_magazines_template_version_id', 'magazines', 'template_versions', ['template_version_id'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_magazines_lab_id'), 'magazines', ['lab_id'], unique=False)

    # 6. Add columns to media
    op.add_column('media', sa.Column('lab_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_media_lab_id', 'media', 'labs', ['lab_id'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_media_lab_id'), 'media', ['lab_id'], unique=False)

    # 7. Add columns to source_documents
    op.add_column('source_documents', sa.Column('lab_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_source_documents_lab_id', 'source_documents', 'labs', ['lab_id'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_source_documents_lab_id'), 'source_documents', ['lab_id'], unique=False)

    # 8. Add columns to template_versions
    op.add_column('template_versions', sa.Column('section_schema_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('template_versions', sa.Column('style_rules_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('template_versions', sa.Column('changelog', sa.Text(), nullable=True))
    op.add_column('template_versions', sa.Column('created_by_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_template_versions_created_by_id', 'template_versions', 'users', ['created_by_id'], ['id'], ondelete='SET NULL')


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
