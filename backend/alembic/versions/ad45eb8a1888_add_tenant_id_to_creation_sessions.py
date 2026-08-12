"""add tenant_id to creation_sessions

修复 creation_sessions 表缺少 tenant_id 字段的问题，
与模型定义保持一致。

Revision ID: ad45eb8a1888
Revises: f1a2b3c4d5e6
"""
from alembic import op
import sqlalchemy as sa


revision = "ad45eb8a1888"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("creation_sessions")}

    if "tenant_id" not in columns:
        with op.batch_alter_table("creation_sessions") as batch:
            batch.add_column(sa.Column("tenant_id", sa.Integer(), nullable=True))
        op.create_index("ix_creation_sessions_tenant_id", "creation_sessions", ["tenant_id"])

    op.execute("""
        UPDATE creation_sessions
        SET tenant_id = (
            SELECT tenant_id FROM users WHERE users.id = creation_sessions.user_id
        )
        WHERE tenant_id IS NULL AND user_id IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_index("ix_creation_sessions_tenant_id", table_name="creation_sessions")
    with op.batch_alter_table("creation_sessions") as batch:
        batch.drop_column("tenant_id")
