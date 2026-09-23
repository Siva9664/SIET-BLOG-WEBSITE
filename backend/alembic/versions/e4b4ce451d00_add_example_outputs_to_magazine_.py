"""add_example_outputs_to_magazine_templates

Revision ID: e4b4ce451d00
Revises: 2801f999c755
Create Date: 2026-08-31 09:14:54.509412

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e4b4ce451d00'
down_revision: Union[str, Sequence[str], None] = '2801f999c755'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE magazine_templates ADD COLUMN IF NOT EXISTS example_outputs JSON;")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('magazine_templates', 'example_outputs')
