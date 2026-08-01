"""add icl_speaker_id to user_voice_profiles

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-01

火山训练成功后返回内部音色 ID (ICL_xxx), 合成时用它而非我方 custom_speaker_id
"""
from alembic import op
import sqlalchemy as sa

revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('user_voice_profiles', sa.Column('icl_speaker_id', sa.String(128), nullable=True))
    op.create_index('ix_user_voice_profiles_icl_speaker_id', 'user_voice_profiles', ['icl_speaker_id'])


def downgrade() -> None:
    op.drop_index('ix_user_voice_profiles_icl_speaker_id', table_name='user_voice_profiles')
    op.drop_column('user_voice_profiles', 'icl_speaker_id')
