"""
Конфигурация приложения FastAPI (замена Django settings.py).
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Core ──────────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("SECRET_KEY", "fastapi-insecure-change-me-in-production")
DEBUG = os.environ.get("DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# ── Database ──────────────────────────────────────────────────────────────────
if os.environ.get("USE_SQLITE", "False").lower() == "true":
    DATABASE_URL = f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
else:
    DB_NAME = os.environ.get("DB_NAME", "tasktracker")
    DB_USER = os.environ.get("DB_USER", "postgres")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = os.environ.get("DB_PORT", "5432")
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# ── Redis & Celery ────────────────────────────────────────────────────────────
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

# ── Session ───────────────────────────────────────────────────────────────────
SESSION_COOKIE_NAME = "session"
SESSION_MAX_AGE = 86400          # 24 ч
REMEMBER_ME_MAX_AGE = 30 * 86400  # 30 дней
INACTIVITY_TIMEOUT = 30 * 60    # 30 мин

# ── Static & Media ───────────────────────────────────────────────────────────
STATIC_DIR = BASE_DIR / "static"
STATIC_URL = "/static"
MEDIA_DIR = BASE_DIR / "media"
MEDIA_URL = "/media"

# ── File uploads ──────────────────────────────────────────────────────────────
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

# ── Templates ─────────────────────────────────────────────────────────────────
TEMPLATES_DIR = BASE_DIR / "templates"

# ── Timezone ──────────────────────────────────────────────────────────────────
TIMEZONE = "Asia/Bishkek"
