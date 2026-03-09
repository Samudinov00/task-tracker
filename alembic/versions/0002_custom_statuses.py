"""Custom kanban statuses per project

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-09 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    # ── project_statuses ──────────────────────────────────────────────────────
    if "project_statuses" not in existing:
        op.create_table(
            "project_statuses",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("color", sa.String(20), nullable=False, server_default="primary"),
            sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_final", sa.Boolean(), nullable=False, server_default="false"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    op.create_index("ix_project_statuses_id", "project_statuses", ["id"], if_not_exists=True)
    op.create_index("ix_project_statuses_project_id", "project_statuses", ["project_id"], if_not_exists=True)

    # ── tasks: add status_id column ───────────────────────────────────────────
    if "tasks" in existing:
        cols = {c["name"] for c in inspector.get_columns("tasks")}
        if "status_id" not in cols:
            op.add_column(
                "tasks",
                sa.Column("status_id", sa.Integer(), nullable=True),
            )
            op.create_foreign_key(
                "fk_tasks_status_id_project_statuses",
                "tasks", "project_statuses",
                ["status_id"], ["id"],
            )

    op.create_index("ix_tasks_status_id", "tasks", ["status_id"], if_not_exists=True)
    op.create_index("task_project_status_idx", "tasks", ["project_id", "status_id"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("task_project_status_idx", table_name="tasks")
    op.drop_index("ix_tasks_status_id", table_name="tasks")
    op.drop_constraint("fk_tasks_status_id_project_statuses", "tasks", type_="foreignkey")
    op.drop_column("tasks", "status_id")
    op.drop_index("ix_project_statuses_project_id", table_name="project_statuses")
    op.drop_index("ix_project_statuses_id", table_name="project_statuses")
    op.drop_table("project_statuses")
