"""Initial schema — все таблицы

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    # ── users ────────────────────────────────────────────────────────────────
    if "users" not in existing:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("username", sa.String(150), nullable=False),
            sa.Column("first_name", sa.String(150), nullable=False, server_default=""),
            sa.Column("last_name", sa.String(150), nullable=False, server_default=""),
            sa.Column("email", sa.String(254), nullable=False, server_default=""),
            sa.Column("hashed_password", sa.String(255), nullable=False),
            sa.Column("role", sa.String(20), nullable=False, server_default="executor"),
            sa.Column("avatar", sa.String(500), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("date_joined", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    op.create_index("ix_users_id", "users", ["id"], if_not_exists=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True, if_not_exists=True)

    # ── projects ──────────────────────────────────────────────────────────────
    if "projects" not in existing:
        op.create_table(
            "projects",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("uuid", sa.CHAR(32), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("manager_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["manager_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("uuid"),
        )
    op.create_index("ix_projects_id", "projects", ["id"], if_not_exists=True)
    op.create_index("ix_projects_uuid", "projects", ["uuid"], if_not_exists=True)

    # ── project_executors (M2M) ───────────────────────────────────────────────
    if "project_executors" not in existing:
        op.create_table(
            "project_executors",
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("project_id", "user_id"),
        )

    # ── project_clients (M2M) ─────────────────────────────────────────────────
    if "project_clients" not in existing:
        op.create_table(
            "project_clients",
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("project_id", "user_id"),
        )

    # ── tasks ─────────────────────────────────────────────────────────────────
    if "tasks" not in existing:
        op.create_table(
            "tasks",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("uuid", sa.CHAR(32), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="not_started"),
            sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
            sa.Column("assignee_id", sa.Integer(), nullable=True),
            sa.Column("created_by_id", sa.Integer(), nullable=False),
            sa.Column("deadline", sa.Date(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
            sa.ForeignKeyConstraint(["assignee_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("uuid"),
        )
    op.create_index("ix_tasks_id", "tasks", ["id"], if_not_exists=True)
    op.create_index("ix_tasks_uuid", "tasks", ["uuid"], if_not_exists=True)
    op.create_index("ix_tasks_status", "tasks", ["status"], if_not_exists=True)
    op.create_index("ix_tasks_created_at", "tasks", ["created_at"], if_not_exists=True)
    op.create_index("ix_tasks_deadline", "tasks", ["deadline"], if_not_exists=True)
    op.create_index("ix_tasks_order", "tasks", ["order"], if_not_exists=True)
    op.create_index("task_project_status_idx", "tasks", ["project_id", "status"], if_not_exists=True)

    # ── task_clients (M2M) ────────────────────────────────────────────────────
    if "task_clients" not in existing:
        op.create_table(
            "task_clients",
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("task_id", "user_id"),
        )

    # ── task_status_logs ──────────────────────────────────────────────────────
    if "task_status_logs" not in existing:
        op.create_table(
            "task_status_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.Column("changed_by_id", sa.Integer(), nullable=True),
            sa.Column("old_status", sa.String(20), nullable=False),
            sa.Column("new_status", sa.String(20), nullable=False),
            sa.Column("changed_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
            sa.ForeignKeyConstraint(["changed_by_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    op.create_index("ix_task_status_log_changed_at", "task_status_logs", ["changed_at"], if_not_exists=True)

    # ── comments ──────────────────────────────────────────────────────────────
    if "comments" not in existing:
        op.create_table(
            "comments",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.Column("author_id", sa.Integer(), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
            sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    # ── notifications ─────────────────────────────────────────────────────────
    if "notifications" not in existing:
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("task_id", sa.Integer(), nullable=True),
            sa.Column("notification_type", sa.String(20), nullable=False),
            sa.Column("message", sa.String(500), nullable=False),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"], if_not_exists=True)
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"], if_not_exists=True)

    # ── task_attachments ──────────────────────────────────────────────────────
    if "task_attachments" not in existing:
        op.create_table(
            "task_attachments",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.Column("file", sa.String(500), nullable=False),
            sa.Column("uploaded_by_id", sa.Integer(), nullable=True),
            sa.Column("uploaded_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
            sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    # ── time_logs ─────────────────────────────────────────────────────────────
    if "time_logs" not in existing:
        op.create_table(
            "time_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("minutes", sa.Integer(), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("logged_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    # ── task_change_logs ──────────────────────────────────────────────────────
    if "task_change_logs" not in existing:
        op.create_table(
            "task_change_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.Column("changed_by_id", sa.Integer(), nullable=False),
            sa.Column("field_name", sa.String(100), nullable=False),
            sa.Column("old_value", sa.Text(), nullable=False, server_default=""),
            sa.Column("new_value", sa.Text(), nullable=False, server_default=""),
            sa.Column("changed_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
            sa.ForeignKeyConstraint(["changed_by_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    op.create_index("ix_task_change_log_task_changed_at", "task_change_logs", ["task_id", "changed_at"], if_not_exists=True)


def downgrade() -> None:
    op.drop_table("task_change_logs")
    op.drop_table("time_logs")
    op.drop_table("task_attachments")
    op.drop_table("notifications")
    op.drop_table("comments")
    op.drop_table("task_status_logs")
    op.drop_table("task_clients")
    op.drop_table("tasks")
    op.drop_table("project_clients")
    op.drop_table("project_executors")
    op.drop_table("projects")
    op.drop_table("users")
