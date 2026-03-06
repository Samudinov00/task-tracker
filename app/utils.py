"""
Утилиты: Jinja2 шаблоны, flash-сообщения, CSRF.
"""
from typing import List, Optional

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.config import TEMPLATES_DIR, STATIC_URL

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# ── Flash-сообщения ───────────────────────────────────────────────────────────

def flash(request: Request, message: str, category: str = "info") -> None:
    """Добавляет flash-сообщение в сессию."""
    if "_messages" not in request.session:
        request.session["_messages"] = []
    msgs = list(request.session["_messages"])
    msgs.append({"message": message, "tags": category})
    request.session["_messages"] = msgs


def get_flashed_messages(request: Request) -> List[dict]:
    """Возвращает и очищает flash-сообщения."""
    msgs = list(request.session.pop("_messages", []))
    return msgs


# ── Jinja2 глобальные функции ─────────────────────────────────────────────────

def static(path: str) -> str:
    """Генерирует URL для статического файла."""
    return f"{STATIC_URL}/{path}"


# Добавляем глобальные функции в Jinja2-окружение
templates.env.globals["static"] = static
templates.env.globals["get_flashed_messages"] = get_flashed_messages
