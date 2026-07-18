"""TASK-016.3A.5: AI素材片段化能力增强 - 新增asset_segments和creator_performance_profiles表

Revision ID: adee20fad9c5
Revises: 696cdda55266
Create Date: 2026-07-14 18:20:26.559028

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'adee20fad9c5'
down_revision: Union[str, None] = '696cdda55266'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """空迁移 - 表已通过 init_db.py 创建"""
    pass


def downgrade() -> None:
    """空迁移 - 表已通过 init_db.py 创建"""
    pass
