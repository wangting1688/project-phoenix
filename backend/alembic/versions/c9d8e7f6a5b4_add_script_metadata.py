"""add script metadata (emphasis words / hot flag)

Revision ID: c9d8e7f6a5b4
Revises: bb6ecd2c645f
Create Date: 2026-09-10
"""
from alembic import op
import sqlalchemy as sa


revision = "c9d8e7f6a5b4"
down_revision = "bb6ecd2c645f"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("scripts", sa.Column("metadata", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("scripts", "metadata")
