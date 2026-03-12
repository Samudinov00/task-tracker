"""Add telegram_username to users

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-09 00:00:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns("users")]

    if "telegram_username" not in columns:
        op.add_column("users", sa.Column("telegram_username", sa.String(100), nullable=True))
        op.create_index("ix_users_telegram_username", "users", ["telegram_username"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_telegram_username", table_name="users")
    op.drop_column("users", "telegram_username")
