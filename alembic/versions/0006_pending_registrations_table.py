"""Add pending_registrations table

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-13 00:00:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "pending_registrations" not in inspector.get_table_names():
        op.create_table(
            "pending_registrations",
            sa.Column("telegram_id", sa.BigInteger(), primary_key=True),
            sa.Column("tg_username", sa.String(100), nullable=True, default=""),
            sa.Column("step", sa.String(50), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("pending_registrations")
