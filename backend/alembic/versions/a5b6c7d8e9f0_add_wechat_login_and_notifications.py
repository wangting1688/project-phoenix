"""add wechat login and notifications

Revision ID: a5b6c7d8e9f0
Revises: c9d8e7f6a5b4
Create Date: 2026-09-12
"""
from alembic import op
import sqlalchemy as sa


revision = "a5b6c7d8e9f0"
down_revision = "c9d8e7f6a5b4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("phone", existing_type=sa.String(20), nullable=True)
        batch_op.add_column(sa.Column("openid", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("unionid", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("wechat_nickname", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("wechat_avatar", sa.String(500), nullable=True))
        batch_op.create_index("ix_users_openid", ["openid"], unique=True)
        batch_op.create_index("ix_users_unionid", ["unionid"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(30), nullable=False, server_default="task"),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("link", sa.String(500), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"])
    op.create_index("ix_notifications_type", "notifications", ["type"])


def downgrade():
    op.drop_table("notifications")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_unionid")
        batch_op.drop_index("ix_users_openid")
        batch_op.drop_column("wechat_avatar")
        batch_op.drop_column("wechat_nickname")
        batch_op.drop_column("unionid")
        batch_op.drop_column("openid")
        batch_op.alter_column("phone", existing_type=sa.String(20), nullable=False)
