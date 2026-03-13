"""Add login_codes table for DB-backed one-time codes

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-13 00:00:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "login_codes" not in inspector.get_table_names():
        op.create_table(
            "login_codes",
            sa.Column("code", sa.String(6), primary_key=True),
            sa.Column("telegram_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("expires", sa.Float(), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("login_codes")
