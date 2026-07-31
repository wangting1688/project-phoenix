"""add user_voice_profiles

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-31T20:15:00.000000

用户声纹档案表, 火山方舟豆包语音 voice cloning 使用.
模型层已定义, 本 migration 幂等建表 (老库 no-op, 新库真建).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("user_voice_profiles"):
        op.create_table(
            "user_voice_profiles",
            sa.Column("user_id", sa.INTEGER(), nullable=False, index=True),
            sa.Column("name", sa.VARCHAR(length=100), nullable=False),
            sa.Column("custom_speaker_id", sa.VARCHAR(length=256), nullable=True, index=True),
            sa.Column("sample_path", sa.VARCHAR(length=500), nullable=False),
            sa.Column("sample_duration", sa.INTEGER(), nullable=True),
            sa.Column("language", sa.INTEGER(), nullable=True, server_default="0"),
            sa.Column("reference_text", sa.TEXT(), nullable=True),
            sa.Column("demo_text", sa.TEXT(), nullable=True),
            sa.Column("status", sa.VARCHAR(length=20), nullable=True, server_default="training", index=True),
            sa.Column("volc_status", sa.INTEGER(), nullable=True, server_default="0"),
            sa.Column("available_training_times", sa.INTEGER(), nullable=True, server_default="0"),
            sa.Column("demo_audio_path", sa.VARCHAR(length=500), nullable=True),
            sa.Column("error_message", sa.VARCHAR(length=500), nullable=True),
            sa.Column("id", sa.INTEGER(), nullable=False, primary_key=True, index=True),
            sa.Column("created_at", sa.DATETIME(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DATETIME(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("user_voice_profiles"):
        op.drop_table("user_voice_profiles")
