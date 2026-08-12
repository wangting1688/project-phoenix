"""add source_type and source_ref to footages

为 footages 表增加素材来源标识，支持系统演示素材、AI生成素材、
合作素材等多种来源类型，配合软删除机制。

Revision ID: f1a2b3c4d5e6
Revises: e7f8a9b0c1d2
Create Date: 2026-08-06
"""
from typing import Union

from alembic import op
import sqlalchemy as sa


revision = 'f1a2b3c4d5e6'
down_revision = 'e7f8a9b0c1d2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. source_type: 素材来源类型
    #    user_upload / system_demo / ai_generated / partner_provided
    op.add_column(
        'footages',
        sa.Column(
            'source_type',
            sa.VARCHAR(length=30),
            nullable=False,
            server_default='user_upload',
        )
    )
    op.create_index(
        'ix_footages_source_type',
        'footages',
        ['source_type'],
    )

    # 2. source_ref: 来源引用标识
    #    系统素材全局编码 / AI生成任务ID / 合作素材编码
    op.add_column(
        'footages',
        sa.Column(
            'source_ref',
            sa.VARCHAR(length=128),
            nullable=True,
        )
    )
    op.create_index(
        'ix_footages_source_ref',
        'footages',
        ['source_ref'],
    )


def downgrade() -> None:
    op.drop_index('ix_footages_source_ref', table_name='footages')
    op.drop_index('ix_footages_source_type', table_name='footages')
    op.drop_column('footages', 'source_ref')
    op.drop_column('footages', 'source_type')
