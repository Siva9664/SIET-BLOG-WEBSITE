"""add_documents_and_template_engine_tables

Revision ID: 2801f999c755
Revises: c9d2e1f4a8b7
Create Date: 2026-08-31 09:10:55.682735

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2801f999c755'
down_revision: Union[str, Sequence[str], None] = 'c9d2e1f4a8b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
