"""
Сброс БД и создание одного менеджера.
Запуск на сервере:
  docker compose exec web python scripts/reset_db.py
"""
import sys
import os

sys.path.insert(0, "/app")

from sqlalchemy import text
from app.database import SessionLocal, Base, engine
from app.models import user as user_mod          # noqa: регистрирует модели
from app.models import project as project_mod    # noqa: регистрирует модели
from app.models.user import User, ROLE_MANAGER
from app.models.project import Project, ProjectStatus, DEFAULT_STATUSES

USERNAME = "admin"
PASSWORD = "Admin1234!"

print("==> Удаляем все таблицы и индексы...")
with engine.connect() as conn:
    # Дропаем осиротевшие таблицы (удалены из моделей, но остались в БД)
    conn.execute(text("DROP TABLE IF EXISTS task_attachments CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS time_logs CASCADE"))
    # Дропаем сталые индексы
    conn.execute(text("DROP INDEX IF EXISTS task_project_status_idx"))
    conn.execute(text("DROP INDEX IF EXISTS ix_tasks_status"))
    conn.commit()

Base.metadata.drop_all(bind=engine)

print("==> Создаём таблицы заново...")
Base.metadata.create_all(bind=engine)

print("==> Создаём пользователя-менеджера...")
db = SessionLocal()
try:
    u = User(
        username=USERNAME,
        first_name="Admin",
        last_name="",
        email="",
        role=ROLE_MANAGER,
        is_active=True,
        is_superuser=True,
    )
    u.set_password(PASSWORD)
    db.add(u)
    db.commit()
    db.refresh(u)
    print(f"\n  Логин:  {USERNAME}")
    print(f"  Пароль: {PASSWORD}")

    print("==> Создаём тестовый проект с дефолтными статусами...")
    project = Project(
        name="Тестовый проект",
        description="Демонстрационный проект, созданный при сбросе БД.",
        manager_id=u.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    for s in DEFAULT_STATUSES:
        status = ProjectStatus(
            project_id=project.id,
            name=s["name"],
            color=s["color"],
            order=s["order"],
            is_final=s["is_final"],
        )
        db.add(status)
    db.commit()
    print(f"  Проект «{project.name}» создан с {len(DEFAULT_STATUSES)} статусами.")
finally:
    db.close()
