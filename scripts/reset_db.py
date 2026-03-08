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

USERNAME = "admin"
PASSWORD = "Admin1234!"

print("==> Удаляем все таблицы и индексы...")
with engine.connect() as conn:
    # Сначала сбрасываем все индексы, которые могут мешать пересозданию
    conn.execute(text("DROP INDEX IF EXISTS task_project_status_idx"))
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
    print(f"\n  Логин:  {USERNAME}")
    print(f"  Пароль: {PASSWORD}")
finally:
    db.close()
