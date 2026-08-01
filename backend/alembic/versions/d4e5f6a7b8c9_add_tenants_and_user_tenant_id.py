"""add tenants table and users.tenant_id

模型 Tenant / User.tenant_id 早已存在, 但迁移链遗漏,
导致全新库缺 tenants 表与 users.tenant_id 列 (登录直接 500)。
本迁移补齐, 使全新部署与既有库一致。

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""
from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "tenants" not in inspector.get_table_names():
        op.create_table(
            "tenants",
            sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("code", sa.String(length=50), nullable=False),
            sa.Column("contact_name", sa.String(length=100), nullable=True),
            sa.Column("contact_phone", sa.String(length=20), nullable=True),
            sa.Column("account", sa.String(length=100), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("status", sa.Integer(), nullable=True),
            sa.Column("max_users", sa.Integer(), nullable=True),
            sa.Column("max_video_projects", sa.Integer(), nullable=True),
            sa.Column("config", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_tenants_id", "tenants", ["id"])
        op.create_index("ix_tenants_code", "tenants", ["code"], unique=True)
        op.create_index("ix_tenants_account", "tenants", ["account"], unique=True)
        op.create_index("ix_tenants_status", "tenants", ["status"])
        op.create_index("ix_tenants_created_at", "tenants", ["created_at"])

    user_columns = {c["name"] for c in inspector.get_columns("users")}
    if "tenant_id" not in user_columns:
        # SQLite 加带外键的列需用 batch_alter_table
        with op.batch_alter_table("users") as batch:
            batch.add_column(sa.Column("tenant_id", sa.Integer(), nullable=True))
        op.create_index("ix_users_tenant_id", "users", ["tenant_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    user_columns = {c["name"] for c in inspector.get_columns("users")}
    if "tenant_id" in user_columns:
        op.drop_index("ix_users_tenant_id", table_name="users")
        with op.batch_alter_table("users") as batch:
            batch.drop_column("tenant_id")

    if "tenants" in inspector.get_table_names():
        op.drop_table("tenants")
