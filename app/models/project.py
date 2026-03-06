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

    def get_progress(self) -> int:
        total = len(self.tasks)
        if total == 0:
            return 0
        done = sum(1 for t in self.tasks if t.status == "production")
        return int(done / total * 100)

    def __str__(self) -> str:
        return self.name


# ── Статусы и приоритеты задачи ───────────────────────────────────────────────
STATUS_NOT_STARTED   = "not_started"
STATUS_DEVELOPMENT   = "development"
STATUS_TEST_NSK      = "test_nsk"
STATUS_TEST_DISTRICT = "test_district"
STATUS_PRODUCTION    = "production"

STATUS_CHOICES = [
    (STATUS_NOT_STARTED,   "Не начата"),
    (STATUS_DEVELOPMENT,   "Разработка"),
    (STATUS_TEST_NSK,      "Тест НСК"),
    (STATUS_TEST_DISTRICT, "Тест район"),
    (STATUS_PRODUCTION,    "Промышленная эксплуатация"),
]

STATUS_BADGE = {
    STATUS_NOT_STARTED:   "secondary",
    STATUS_DEVELOPMENT:   "primary",
    STATUS_TEST_NSK:      "warning",
    STATUS_TEST_DISTRICT: "warning",
    STATUS_PRODUCTION:    "success",
}

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


# ── Задача ────────────────────────────────────────────────────────────────────
class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("task_project_status_idx", "project_id", "status"),
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_created_at", "created_at"),
        Index("ix_tasks_deadline", "deadline"),
        Index("ix_tasks_order", "order"),
    )

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID, default=uuid.uuid4, unique=True, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    status = Column(String(20), default=STATUS_NOT_STARTED, nullable=False)
    priority = Column(String(20), default=PRIORITY_MEDIUM, nullable=False)
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    deadline = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    order = Column(Integer, default=0)

    project = relationship("Project", back_populates="tasks")
    assignee = relationship("User", foreign_keys=[assignee_id], backref="assigned_tasks")
    created_by = relationship("User", foreign_keys=[created_by_id], backref="created_tasks")
    clients = relationship("User", secondary=task_clients, backref="client_tasks")
    comments = relationship("Comment", back_populates="task", cascade="all, delete-orphan", order_by="Comment.created_at")
    status_logs = relationship("TaskStatusLog", back_populates="task", cascade="all, delete-orphan")
    change_logs = relationship("TaskChangeLog", back_populates="task", cascade="all, delete-orphan")
    attachments = relationship("TaskAttachment", back_populates="task", cascade="all, delete-orphan")
    time_logs = relationship("TimeLog", back_populates="task", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="task", cascade="all, delete-orphan")

    def get_status_badge(self) -> str:
        return STATUS_BADGE.get(self.status, "secondary")

    def get_priority_badge(self) -> str:
        return PRIORITY_BADGE.get(self.priority, "secondary")

    def get_priority_icon(self) -> str:
        return PRIORITY_ICON.get(self.priority, "bi-dash")

    def get_status_display(self) -> str:
        return dict(STATUS_CHOICES).get(self.status, self.status)

    def get_priority_display(self) -> str:
        return dict(PRIORITY_CHOICES).get(self.priority, self.priority)

    def is_overdue(self) -> bool:
        if self.deadline and self.status != STATUS_PRODUCTION:
            return self.deadline < date.today()
        return False

    def get_total_logged_minutes(self) -> int:
        return sum(tl.minutes for tl in self.time_logs)

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
    old_status = Column(String(20), nullable=False)
    new_status = Column(String(20), nullable=False)
    changed_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="status_logs")
    changed_by = relationship("User", foreign_keys=[changed_by_id])

    def get_old_status_display(self) -> str:
        return dict(STATUS_CHOICES).get(self.old_status, self.old_status)

    def get_new_status_display(self) -> str:
        return dict(STATUS_CHOICES).get(self.new_status, self.new_status)


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


# ── Вложения к задаче ─────────────────────────────────────────────────────────
class TaskAttachment(Base):
    __tablename__ = "task_attachments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    file = Column(String(500), nullable=False)  # relative path
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="attachments")
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_id])

    def filename(self) -> str:
        return os.path.basename(self.file)


# ── Трекер времени ────────────────────────────────────────────────────────────
class TimeLog(Base):
    __tablename__ = "time_logs"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    minutes = Column(Integer, nullable=False)
    description = Column(Text, default="")
    logged_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="time_logs")
    user = relationship("User", foreign_keys=[user_id])


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
