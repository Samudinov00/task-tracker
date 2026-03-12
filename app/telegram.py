"""
Утилиты для Telegram Bot API:
- отправка уведомлений пользователям
- валидация Telegram Login Widget
"""
import hashlib
import hmac
import secrets
import time
import logging
from typing import Optional

import httpx

from app.config import TELEGRAM_BOT_TOKEN, SITE_URL

# ── Коды входа через бота (in-memory, TTL 5 минут) ───────────────────────────
_login_codes: dict = {}  # code → {"telegram_id": int, "expires": float}


def generate_login_code(telegram_id: int) -> str:
    """Генерирует 6-значный код входа для telegram_id."""
    code = str(secrets.randbelow(900000) + 100000)
    _login_codes[code] = {"telegram_id": telegram_id, "expires": time.time() + 300}
    return code


def validate_login_code(code: str) -> Optional[int]:
    """Проверяет код входа. Возвращает telegram_id или None."""
    entry = _login_codes.get(code)
    if not entry:
        return None
    if time.time() > entry["expires"]:
        del _login_codes[code]
        return None
    telegram_id = entry["telegram_id"]
    del _login_codes[code]
    return telegram_id

logger = logging.getLogger(__name__)

_TG_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


# ── Отправка сообщений ────────────────────────────────────────────────────────

def send_message(telegram_id: int, text: str) -> bool:
    """Отправить сообщение пользователю. Возвращает True при успехе."""
    if not TELEGRAM_BOT_TOKEN or not telegram_id:
        return False
    try:
        resp = httpx.post(
            f"{_TG_API}/sendMessage",
            json={"chat_id": telegram_id, "text": text, "parse_mode": "HTML"},
            timeout=5,
        )
        return resp.status_code == 200
    except Exception as e:
        logger.warning("Telegram sendMessage failed: %s", e)
        return False


def notify_task_assigned(assignee_telegram_id: int, task_title: str,
                         project_name: str, task_uuid: str) -> None:
    """Уведомить исполнителя о назначении задачи."""
    url = f"{SITE_URL}/t/{task_uuid}/"
    text = (
        f"📋 <b>Вам назначена задача</b>\n\n"
        f"<b>{task_title}</b>\n"
        f"Проект: {project_name}\n\n"
        f'<a href="{url}">Открыть задачу</a>'
    )
    send_message(assignee_telegram_id, text)


def notify_task_status_changed(telegram_id: int, task_title: str,
                                old_status: str, new_status: str,
                                task_uuid: str) -> None:
    """Уведомить о смене статуса задачи."""
    url = f"{SITE_URL}/t/{task_uuid}/"
    text = (
        f"🔄 <b>Статус задачи изменён</b>\n\n"
        f"<b>{task_title}</b>\n"
        f"{old_status} → <b>{new_status}</b>\n\n"
        f'<a href="{url}">Открыть задачу</a>'
    )
    send_message(telegram_id, text)


def notify_deadline_reminder(telegram_id: int, task_title: str,
                              project_name: str, deadline_str: str,
                              task_uuid: str) -> None:
    """Напоминание о приближающемся дедлайне."""
    url = f"{SITE_URL}/t/{task_uuid}/"
    text = (
        f"⏰ <b>Дедлайн задачи приближается</b>\n\n"
        f"<b>{task_title}</b>\n"
        f"Проект: {project_name}\n"
        f"Дедлайн: {deadline_str}\n\n"
        f'<a href="{url}">Открыть задачу</a>'
    )
    send_message(telegram_id, text)


# ── Валидация Telegram Login Widget ──────────────────────────────────────────

def validate_telegram_auth(data: dict) -> bool:
    """
    Проверяет подпись данных от Telegram Login Widget.
    https://core.telegram.org/widgets/login#checking-authorization
    """
    if not TELEGRAM_BOT_TOKEN:
        return False

    received_hash = data.get("hash", "")
    auth_date = int(data.get("auth_date", 0))

    # Проверяем что данные не старше 24 часов
    if time.time() - auth_date > 86400:
        return False

    # Строим строку для проверки (все поля кроме hash, отсортированные)
    fields = {k: v for k, v in data.items() if k != "hash"}
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))

    # Секретный ключ = SHA256 от токена бота
    secret_key = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode()).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    return computed_hash == received_hash
