"""
Модель пользователя (замена CustomUser из accounts/models.py).
"""
import uuid as uuid_lib
from datetime import datetime

from passlib.context import CryptContext
from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ROLE_MANAGER = "manager"
ROLE_EXECUTOR = "executor"
ROLE_CLIENT = "client"

ROLE_LABELS = {
    ROLE_MANAGER: "Менеджер",
    ROLE_EXECUTOR: "Исполнитель",
    ROLE_CLIENT: "Клиент",
}


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(150), unique=True, nullable=False, index=True)
    first_name = Column(String(150), default="")
    last_name = Column(String(150), default="")
    email = Column(String(254), default="")
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default=ROLE_EXECUTOR, nullable=False)
    avatar = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    date_joined = Column(DateTime, default=datetime.utcnow)
    telegram_id       = Column(BigInteger, unique=True, nullable=True, index=True)
    telegram_username = Column(String(100), unique=True, nullable=True, index=True)

    # relationships (back-referenced from project.py)
    managed_projects = relationship("Project", back_populates="manager", foreign_keys="Project.manager_id")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def verify_password(self, plain: str) -> bool:
        return pwd_context.verify(plain, self.hashed_password)

    def set_password(self, plain: str) -> None:
        self.hashed_password = pwd_context.hash(plain)

    @property
    def is_authenticated(self) -> bool:
        return True

    def is_manager(self) -> bool:
        return self.role == ROLE_MANAGER

    def is_executor(self) -> bool:
        return self.role == ROLE_EXECUTOR

    def is_client(self) -> bool:
        return self.role == ROLE_CLIENT

    def get_initials(self) -> str:
        if self.first_name and self.last_name:
            return f"{self.first_name[0]}{self.last_name[0]}".upper()
        return self.username[:2].upper()

    def get_display_name(self) -> str:
        full = f"{self.first_name} {self.last_name}".strip()
        return full if full else self.username

    def get_full_name(self) -> str:
        return self.get_display_name()

    def get_role_display(self) -> str:
        return ROLE_LABELS.get(self.role, self.role)

    def __repr__(self) -> str:
        return f"<User {self.username}>"
