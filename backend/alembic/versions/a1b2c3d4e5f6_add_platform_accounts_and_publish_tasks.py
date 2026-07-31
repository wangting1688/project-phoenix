"""add platform_accounts and publish_tasks

Revision ID: a1b2c3d4e5f6
Revises: aa266b3edc17
Create Date: 2026-07-31T14:10:26.651531

物理 schema 与 model 已对齐 (新增模块时已通过 SQL 同步), 本 migration
对历史 DB 是 no-op; 对新部署 (空库) 才会真正建表. 幂等.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'aa266b3edc17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # ---- platform_accounts ----
    if not insp.has_table("platform_accounts"):
        op.create_table(
            "platform_accounts",
            sa.Column("user_id", sa.INTEGER(), nullable=False, index=True),
            sa.Column("platform", sa.VARCHAR(length=50), nullable=False, index=True),
            sa.Column("account_name", sa.VARCHAR(length=200), nullable=False),
            sa.Column("account_id", sa.VARCHAR(length=200), nullable=True),
            sa.Column("account_url", sa.VARCHAR(length=500), nullable=True),
            sa.Column("auth_token", sa.TEXT(), nullable=True),
            sa.Column("refresh_token", sa.TEXT(), nullable=True),
            sa.Column("token_expires_at", sa.DATETIME(), nullable=True),
            sa.Column("status", sa.VARCHAR(length=20), nullable=True, server_default="active"),
            sa.Column("follower_count", sa.INTEGER(), nullable=True, server_default="0"),
            sa.Column("follower_gender_ratio", sa.JSON(), nullable=True),
            sa.Column("follower_age_distribution", sa.JSON(), nullable=True),
            sa.Column("follower_region_top", sa.JSON(), nullable=True),
            sa.Column("content_style", sa.VARCHAR(length=50), nullable=True),
            sa.Column("avg_video_duration", sa.INTEGER(), nullable=True),
            sa.Column("best_publish_time", sa.JSON(), nullable=True),
            sa.Column("last_7d_plays", sa.INTEGER(), nullable=True, server_default="0"),
            sa.Column("last_7d_likes", sa.INTEGER(), nullable=True, server_default="0"),
            sa.Column("last_7d_comments", sa.INTEGER(), nullable=True, server_default="0"),
            sa.Column("last_7d_shares", sa.INTEGER(), nullable=True, server_default="0"),
            sa.Column("avg_completion_rate", sa.INTEGER(), nullable=True),
            sa.Column("strategy_config", sa.JSON(), nullable=True),
            sa.Column("last_sync_at", sa.DATETIME(), nullable=True),
            sa.Column("id", sa.INTEGER(), nullable=False, primary_key=True, index=True),
            sa.Column("created_at", sa.DATETIME(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DATETIME(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_platform_accounts_user_id"),
        )

    # ---- publish_tasks ----
    if not insp.has_table("publish_tasks"):
        op.create_table(
            "publish_tasks",
            sa.Column("user_id", sa.INTEGER(), nullable=False, index=True),
            sa.Column("video_project_id", sa.INTEGER(), nullable=True),
            sa.Column("content_title", sa.VARCHAR(length=200), nullable=False),
            sa.Column("content_description", sa.TEXT(), nullable=True),
            sa.Column("platform_account_id", sa.INTEGER(), nullable=False, index=True),
            sa.Column("platform", sa.VARCHAR(length=50), nullable=False, index=True),
            sa.Column("scheduled_at", sa.DATETIME(), nullable=True),
            sa.Column("published_at", sa.DATETIME(), nullable=True),
            sa.Column("status", sa.VARCHAR(length=30), nullable=True, server_default="draft"),
            sa.Column("video_url", sa.VARCHAR(length=500), nullable=True),
            sa.Column("cover_url", sa.VARCHAR(length=500), nullable=True),
            sa.Column("tags", sa.JSON(), nullable=True),
            sa.Column("category", sa.VARCHAR(length=50), nullable=True),
            sa.Column("platform_post_id", sa.VARCHAR(length=200), nullable=True),
            sa.Column("platform_post_url", sa.VARCHAR(length=500), nullable=True),
            sa.Column("publish_error", sa.TEXT(), nullable=True),
            sa.Column("metrics_collected_at", sa.DATETIME(), nullable=True),
            sa.Column("play_count", sa.INTEGER(), nullable=True, server_default="0"),
            sa.Column("like_count", sa.INTEGER(), nullable=True, server_default="0"),
            sa.Column("comment_count", sa.INTEGER(), nullable=True, server_default="0"),
            sa.Column("share_count", sa.INTEGER(), nullable=True, server_default="0"),
            sa.Column("collect_count", sa.INTEGER(), nullable=True, server_default="0"),
            sa.Column("follower_gained", sa.INTEGER(), nullable=True, server_default="0"),
            sa.Column("completion_rate", sa.FLOAT(), nullable=True),
            sa.Column("ctr", sa.FLOAT(), nullable=True),
            sa.Column("growth_insight", sa.JSON(), nullable=True),
            sa.Column("processed_by_graph", sa.INTEGER(), nullable=True, server_default="0"),
            sa.Column("review_status", sa.VARCHAR(length=20), nullable=True, server_default="auto"),
            sa.Column("review_comment", sa.TEXT(), nullable=True),
            sa.Column("id", sa.INTEGER(), nullable=False, primary_key=True, index=True),
            sa.Column("created_at", sa.DATETIME(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DATETIME(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_publish_tasks_user_id"),
            sa.ForeignKeyConstraint(["video_project_id"], ["video_projects.id"], name="fk_publish_tasks_video_project_id"),
            sa.ForeignKeyConstraint(["platform_account_id"], ["platform_accounts.id"], name="fk_publish_tasks_platform_account_id"),
        )


def downgrade() -> None:
    op.drop_table("publish_tasks")
    op.drop_table("platform_accounts")
