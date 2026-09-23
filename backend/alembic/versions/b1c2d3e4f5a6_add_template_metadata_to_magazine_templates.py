"""add_template_metadata_to_magazine_templates

Revision ID: b1c2d3e4f5a6
Revises: 9bb21e575d87
Create Date: 2026-09-13 09:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = '9bb21e575d87'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add template_metadata JSON column to magazine_templates."""
    op.add_column('magazine_templates', sa.Column('template_metadata', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema: remove template_metadata column."""
    op.drop_column('magazine_templates', 'template_metadata')
