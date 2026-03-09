"""
Модели проектов и задач (замена projects/models.py).
"""
import os
import uuid as uuid_lib
from datetime import date, datetime

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Index,
    Integer, String, Table, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator, CHAR
import uuid

from app.database import Base


# ── UUID-совместимый тип (SQLite + PostgreSQL) ────────────────────────────────
class GUID(TypeDecorator):
    """Хранит UUID как CHAR(32) в SQLite и как UUID в PostgreSQL."""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID())
        return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        if isinstance(value, uuid.UUID):
            return value.hex
        return uuid.UUID(value).hex

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(value)
        return value


# ── M2M: проект ↔ исполнители ─────────────────────────────────────────────────
project_executors = Table(
    "project_executors",
    Base.metadata,
    Column("project_id", Integer, ForeignKey("projects.id"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
)

# ── M2M: проект ↔ клиенты ────────────────────────────────────────────────────
project_clients = Table(
    "project_clients",
    Base.metadata,
    Column("project_id", Integer, ForeignKey("projects.id"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
)

# ── M2M: задача ↔ клиенты ────────────────────────────────────────────────────
task_clients = Table(
    "task_clients",
    Base.metadata,
    Column("task_id", Integer, ForeignKey("tasks.id"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
)


# ── Цвета статусов и дефолтные статусы ───────────────────────────────────────
STATUS_COLOR_CHOICES = [
    ("primary",   "Синий"),
    ("secondary", "Серый"),
    ("success",   "Зелёный"),
    ("danger",    "Красный"),
    ("warning",   "Жёлтый"),
    ("info",      "Голубой"),
    ("dark",      "Тёмный"),
]

DEFAULT_STATUSES = [
    {"name": "Разработка",                "color": "primary",   "order": 0, "is_final": False},
    {"name": "Тест НСК",                  "color": "warning",   "order": 1, "is_final": False},
    {"name": "Тест район",                "color": "warning",   "order": 2, "is_final": False},
    {"name": "Промышленная эксплуатация", "color": "success",   "order": 3, "is_final": True},
]


# ── Приоритеты задачи ─────────────────────────────────────────────────────────
PRIORITY_LOW      = "low"
PRIORITY_MEDIUM   = "medium"
PRIORITY_HIGH     = "high"
PRIORITY_CRITICAL = "critical"

PRIORITY_CHOICES = [
    (PRIORITY_LOW,      "Низкий"),
    (PRIORITY_MEDIUM,   "Средний"),
    (PRIORITY_HIGH,     "Высокий"),
    (PRIORITY_CRITICAL, "Критический"),
]

PRIORITY_BADGE = {
    PRIORITY_LOW:      "success",
    PRIORITY_MEDIUM:   "warning",
    PRIORITY_HIGH:     "orange",
    PRIORITY_CRITICAL: "danger",
}

PRIORITY_ICON = {
    PRIORITY_LOW:      "bi-arrow-down",
    PRIORITY_MEDIUM:   "bi-dash",
    PRIORITY_HIGH:     "bi-arrow-up",
    PRIORITY_CRITICAL: "bi-exclamation-triangle-fill",
}


# ── Статус проекта (канбан-колонка) ───────────────────────────────────────────
class ProjectStatus(Base):
    __tablename__ = "project_statuses"

    id         = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name       = Column(String(100), nullable=False)
    color      = Column(String(20), default="primary", nullable=False)
    order      = Column(Integer, default=0, nullable=False)
    is_final   = Column(Boolean, default=False, nullable=False)

    project = relationship("Project", back_populates="statuses")
    tasks   = relationship("Task", back_populates="status_obj")

    def get_icon(self) -> str:
        icons = {
            "primary":   "bi-circle-fill",
            "secondary": "bi-dash-circle-fill",
            "success":   "bi-check-circle-fill",
            "danger":    "bi-x-circle-fill",
            "warning":   "bi-exclamation-circle-fill",
            "info":      "bi-info-circle-fill",
            "dark":      "bi-record-circle-fill",
        }
        return icons.get(self.color, "bi-circle-fill")

    def __str__(self) -> str:
        return self.name


# ── Проект ────────────────────────────────────────────────────────────────────
class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID, default=uuid.uuid4, unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    manager = relationship("User", back_populates="managed_projects", foreign_keys=[manager_id])
    executors = relationship("User", secondary=project_executors, backref="executor_projects")
    clients = relationship("User", secondary=project_clients, backref="client_projects")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    statuses = relationship(
        "ProjectStatus", back_populates="project",
        order_by="ProjectStatus.order",
        cascade="all, delete-orphan",
    )

    def get_progress(self) -> int:
        total = len(self.tasks)
        if total == 0:
            return 0
        done = sum(1 for t in self.tasks if t.status_obj and t.status_obj.is_final)
        return int(done / total * 100)

    def __str__(self) -> str:
        return self.name


# ── Задача ────────────────────────────────────────────────────────────────────
class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("task_project_status_idx", "project_id", "status_id"),
        Index("ix_tasks_status_id", "status_id"),
        Index("ix_tasks_created_at", "created_at"),
        Index("ix_tasks_deadline", "deadline"),
        Index("ix_tasks_order", "order"),
    )

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID, default=uuid.uuid4, unique=True, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    status_id = Column(Integer, ForeignKey("project_statuses.id"), nullable=True)
    priority = Column(String(20), default=PRIORITY_MEDIUM, nullable=False)
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    deadline = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    order = Column(Integer, default=0)

    project = relationship("Project", back_populates="tasks")
    status_obj = relationship("ProjectStatus", back_populates="tasks", foreign_keys=[status_id])
    assignee = relationship("User", foreign_keys=[assignee_id], backref="assigned_tasks")
    created_by = relationship("User", foreign_keys=[created_by_id], backref="created_tasks")
    clients = relationship("User", secondary=task_clients, backref="client_tasks")
    comments = relationship("Comment", back_populates="task", cascade="all, delete-orphan", order_by="Comment.created_at")
    status_logs = relationship("TaskStatusLog", back_populates="task", cascade="all, delete-orphan")
    change_logs = relationship("TaskChangeLog", back_populates="task", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="task", cascade="all, delete-orphan")

    def get_status_badge(self) -> str:
        if self.status_obj:
            return self.status_obj.color
        return "secondary"

    def get_priority_badge(self) -> str:
        return PRIORITY_BADGE.get(self.priority, "secondary")

    def get_priority_icon(self) -> str:
        return PRIORITY_ICON.get(self.priority, "bi-dash")

    def get_status_display(self) -> str:
        if self.status_obj:
            return self.status_obj.name
        return "—"

    def get_priority_display(self) -> str:
        return dict(PRIORITY_CHOICES).get(self.priority, self.priority)

    def is_overdue(self) -> bool:
        if self.deadline and not (self.status_obj and self.status_obj.is_final):
            return self.deadline < date.today()
        return False

    def __str__(self) -> str:
        return self.title


# ── Лог смены статусов ────────────────────────────────────────────────────────
class TaskStatusLog(Base):
    __tablename__ = "task_status_logs"
    __table_args__ = (
        Index("ix_task_status_log_changed_at", "changed_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    changed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    old_status = Column(String(200), nullable=False)
    new_status = Column(String(200), nullable=False)
    changed_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="status_logs")
    changed_by = relationship("User", foreign_keys=[changed_by_id])

    def get_old_status_display(self) -> str:
        return self.old_status

    def get_new_status_display(self) -> str:
        return self.new_status


# ── Комментарий ───────────────────────────────────────────────────────────────
class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="comments")
    author = relationship("User", foreign_keys=[author_id])


# ── Уведомления ───────────────────────────────────────────────────────────────
TYPE_TASK_ASSIGNED = "task_assigned"
TYPE_TASK_STATUS   = "task_status"
TYPE_COMMENT       = "comment"

NOTIFICATION_TYPE_CHOICES = [
    (TYPE_TASK_ASSIGNED, "Назначена задача"),
    (TYPE_TASK_STATUS,   "Изменён статус"),
    (TYPE_COMMENT,       "Новый комментарий"),
]


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_is_read", "is_read"),
        Index("ix_notifications_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    notification_type = Column(String(20), default=TYPE_COMMENT, nullable=False)
    message = Column(String(500), nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id], backref="notifications")
    task = relationship("Task", back_populates="notifications")


# ── История изменений задачи ──────────────────────────────────────────────────
class TaskChangeLog(Base):
    __tablename__ = "task_change_logs"
    __table_args__ = (
        Index("ix_task_change_log_task_changed_at", "task_id", "changed_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    changed_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    field_name = Column(String(100), nullable=False)
    old_value = Column(Text, default="")
    new_value = Column(Text, default="")
    changed_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="change_logs")
    changed_by = relationship("User", foreign_keys=[changed_by_id])
