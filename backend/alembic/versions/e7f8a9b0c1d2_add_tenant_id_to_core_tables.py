"""add tenant_id to content_projects and workflow_tasks

为核心业务表增加租户ID，建立数据库层面的租户隔离基础。
通过 users.tenant_id 回填已有数据。

Revision ID: e7f8a9b0c1d2
Revises: d4e5f6a7b8c9
"""
from alembic import op
import sqlalchemy as sa


revision = "e7f8a9b0c1d2"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name in ["content_projects", "workflow_tasks"]:
        columns = {c["name"] for c in inspector.get_columns(table_name)}
        if "tenant_id" not in columns:
            with op.batch_alter_table(table_name) as batch:
                batch.add_column(sa.Column("tenant_id", sa.Integer(), nullable=True))
            op.create_index(f"ix_{table_name}_tenant_id", table_name, ["tenant_id"])

    # 回填已有数据的 tenant_id（通过 user_id 关联 users 表）
    for table_name in ["content_projects", "workflow_tasks"]:
        # workflow_tasks 没有直接的 user_id，通过 project_id 关联
        if table_name == "content_projects":
            op.execute(f"""
                UPDATE {table_name}
                SET tenant_id = (
                    SELECT tenant_id FROM users WHERE users.id = {table_name}.user_id
                )
                WHERE tenant_id IS NULL AND user_id IS NOT NULL
            """)
        else:
            op.execute(f"""
                UPDATE {table_name}
                SET tenant_id = (
                    SELECT cp.tenant_id FROM content_projects cp
                    WHERE cp.id = {table_name}.project_id
                )
                WHERE tenant_id IS NULL AND project_id IS NOT NULL
            """)


def downgrade() -> None:
    for table_name in ["content_projects", "workflow_tasks"]:
        op.drop_index(f"ix_{table_name}_tenant_id", table_name=table_name)
        with op.batch_alter_table(table_name) as batch:
            batch.drop_column("tenant_id")
