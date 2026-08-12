"""add_deleted_at_to_content_projects

Revision ID: bb6ecd2c645f
Revises: ad45eb8a1888
Create Date: 2026-08-07 15:16:05.502713

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bb6ecd2c645f'
down_revision: Union[str, None] = 'ad45eb8a1888'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('content_projects', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index(
        op.f('ix_content_projects_deleted_at'),
        'content_projects',
        ['deleted_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_content_projects_deleted_at'), table_name='content_projects')
    op.drop_column('content_projects', 'deleted_at')
