"""add source_url and source_name to news

Revision ID: a8f3b2e91c4d
Revises: 7167703dce38
Create Date: 2026-08-03 08:56:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8f3b2e91c4d'
down_revision: Union[str, Sequence[str], None] = '7167703dce38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('news', sa.Column('source_url', sa.String(length=500), nullable=True))
    op.add_column('news', sa.Column('source_name', sa.String(length=100), nullable=True))
    op.create_index(op.f('ix_news_source_url'), 'news', ['source_url'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_news_source_url'), table_name='news')
    op.drop_column('news', 'source_name')
    op.drop_column('news', 'source_url')
