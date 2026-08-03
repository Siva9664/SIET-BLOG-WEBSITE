"""create site_settings table and seed default row

Revision ID: c9d2e1f4a8b7
Revises: a8f3b2e91c4d
Create Date: 2026-08-03 09:37:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9d2e1f4a8b7'
down_revision: Union[str, Sequence[str], None] = 'a8f3b2e91c4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    site_settings_table = op.create_table(
        'site_settings',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('site_name', sa.String(length=200), nullable=False),
        sa.Column('credit_line', sa.Text(), nullable=False),
        sa.Column('accent_color', sa.String(length=50), nullable=False),
        sa.Column('newsletter_enabled', sa.Boolean(), nullable=False),
        sa.Column('featured_domains', sa.String(length=500), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )

    op.bulk_insert(
        site_settings_table,
        [
            {
                'id': 1,
                'site_name': 'SIET News',
                'credit_line': 'AI Research Lab · Sri Shakthi Institute of Engineering and Technology',
                'accent_color': '#0F2B5C',
                'newsletter_enabled': True,
                'featured_domains': 'machine-learning, robotics',
            }
        ]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('site_settings')
