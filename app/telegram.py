"""
Утилиты для Telegram Bot API:
- отправка уведомлений пользователям
- валидация Telegram Login Widget
"""
import hashlib
import hmac
import secrets
import threading
import time
import logging
from typing import Optional

import httpx

from app.config import TELEGRAM_BOT_TOKEN, SITE_URL

# ── Хелперы для pending_registrations в БД ───────────────────────────────────

def get_pending_reg(telegram_id: int):
    from app.database import SessionLocal
    from app.models.user import PendingRegistration
    db = SessionLocal()
    try:
        return db.query(PendingRegistration).filter(PendingRegistration.telegram_id == telegram_id).first()
    finally:
        db.close()


def set_pending_reg(telegram_id: int, tg_username: str, step: str) -> None:
    from app.database import SessionLocal
    from app.models.user import PendingRegistration
    db = SessionLocal()
    try:
        existing = db.query(PendingRegistration).filter(PendingRegistration.telegram_id == telegram_id).first()
        if existing:
            existing.step = step
            existing.tg_username = tg_username
        else:
            db.add(PendingRegistration(telegram_id=telegram_id, tg_username=tg_username, step=step))
        db.commit()
    finally:
        db.close()


def delete_pending_reg(telegram_id: int) -> None:
    from app.database import SessionLocal
    from app.models.user import PendingRegistration
    db = SessionLocal()
    try:
        db.query(PendingRegistration).filter(PendingRegistration.telegram_id == telegram_id).delete()
        db.commit()
    finally:
        db.close()


def generate_login_code(telegram_id: int) -> str:
    """Генерирует 6-значный код входа и сохраняет его в БД (TTL 5 минут)."""
    from app.database import SessionLocal
    from app.models.user import LoginCode
    code = str(secrets.randbelow(900000) + 100000)
    db = SessionLocal()
    try:
        # Удаляем старые коды для этого пользователя и истёкшие
        db.query(LoginCode).filter(
            (LoginCode.telegram_id == telegram_id) | (LoginCode.expires < time.time())
        ).delete()
        db.add(LoginCode(code=code, telegram_id=telegram_id, expires=time.time() + 300))
        db.commit()
    finally:
        db.close()
    return code


def validate_login_code(code: str) -> Optional[int]:
    """Проверяет код входа из БД. Возвращает telegram_id или None."""
    from app.database import SessionLocal
    from app.models.user import LoginCode
    db = SessionLocal()
    try:
        entry = db.query(LoginCode).filter(LoginCode.code == code).first()
        if not entry:
            return None
        if time.time() > entry.expires:
            db.delete(entry)
            db.commit()
            return None
        telegram_id = entry.telegram_id
        db.delete(entry)
        db.commit()
        return telegram_id
    finally:
        db.close()


# ── Клавиатуры ───────────────────────────────────────────────────────────────

def _inline_kb(*rows):
    """Строит InlineKeyboardMarkup из списка списков (text, callback_data)."""
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in rows]}


def _reply_kb(*buttons, one_time=False):
    """Строит ReplyKeyboardMarkup."""
    return {
        "keyboard": [[{"text": b} for b in row] for row in buttons],
        "resize_keyboard": True,
        "one_time_keyboard": one_time,
    }


def _contact_kb():
    """Кнопка запроса номера телефона (Telegram отправляет его автоматически)."""
    return {
        "keyboard": [
            [{"text": "📱 Поделиться номером", "request_contact": True}],
            [{"text": "Отмена"}],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


logger = logging.getLogger(__name__)

_TG_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


# ── Отправка сообщений ────────────────────────────────────────────────────────

def send_message(telegram_id: int, text: str, reply_markup: dict = None) -> Optional[int]:
    """Отправить сообщение пользователю. Возвращает message_id или None."""
    if not TELEGRAM_BOT_TOKEN or not telegram_id:
        return None
    try:
        payload = {"chat_id": telegram_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        resp = httpx.post(f"{_TG_API}/sendMessage", json=payload, timeout=5)
        if resp.status_code == 200:
            return resp.json().get("result", {}).get("message_id")
        return None
    except Exception as e:
        logger.warning("Telegram sendMessage failed: %s", e)
        return None


def delete_message(telegram_id: int, message_id: int) -> None:
    """Удалить сообщение из чата."""
    if not TELEGRAM_BOT_TOKEN:
        return
    try:
        httpx.post(
            f"{_TG_API}/deleteMessage",
            json={"chat_id": telegram_id, "message_id": message_id},
            timeout=5,
        )
    except Exception:
        pass


def _schedule_delete(telegram_id: int, message_id: int, delay: int = 1800) -> None:
    """Запланировать удаление сообщения через delay секунд (по умолчанию 30 мин)."""
    def _do():
        delete_message(telegram_id, message_id)
    t = threading.Timer(delay, _do)
    t.daemon = True
    t.start()


def send_notification(telegram_id: int, text: str) -> None:
    """Отправить уведомление и автоматически удалить его через 30 минут."""
    message_id = send_message(telegram_id, text)
    if message_id:
        _schedule_delete(telegram_id, message_id)


def answer_callback(callback_query_id: str, text: str = "") -> None:
    """Ответить на нажатие inline-кнопки."""
    if not TELEGRAM_BOT_TOKEN:
        return
    try:
        httpx.post(
            f"{_TG_API}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id, "text": text},
            timeout=3,
        )
    except Exception:
        pass


def notify_managers_registration(applicant_id: int, applicant_username: str,
                                  applicant_name: str) -> None:
    """Уведомить всех менеджеров о новой заявке на регистрацию."""
    from app.database import SessionLocal
    from app.models.user import User, ROLE_MANAGER
    db = SessionLocal()
    try:
        managers = db.query(User).filter(
            User.role == ROLE_MANAGER,
            User.telegram_id.isnot(None),
            User.is_active == True,
        ).all()
        username_str = f"@{applicant_username}" if applicant_username else "—"
        text = (
            f"🆕 <b>Новая заявка на регистрацию</b>\n\n"
            f"👤 Имя: <b>{applicant_name}</b>\n"
            f"📱 Username: {username_str}\n"
            f"🆔 Telegram ID: <code>{applicant_id}</code>\n\n"
            f"Для добавления пользователя в систему укажите его Telegram ID:\n"
            f"<b>{applicant_id}</b>"
        )
        for m in managers:
            send_message(m.telegram_id, text)
    finally:
        db.close()


def _notify_many(telegram_ids: list, text: str) -> None:
    """Отправить уведомление нескольким пользователям (дедупликация)."""
    seen = set()
    for tid in telegram_ids:
        if tid and tid not in seen:
            seen.add(tid)
            send_notification(tid, text)


def notify_task_assigned(assignee_telegram_id: int, task_title: str,
                         project_name: str, task_uuid: str,
                         manager_telegram_id: int = None) -> None:
    """Уведомить исполнителя и менеджера о назначении задачи."""
    url = f"{SITE_URL}/t/{task_uuid}/"
    assignee_text = (
        f"📋 <b>Вам назначена задача</b>\n\n"
        f"<b>{task_title}</b>\n"
        f"Проект: {project_name}\n\n"
        f'<a href="{url}">Открыть задачу</a>'
    )
    manager_text = (
        f"📋 <b>Задача назначена исполнителю</b>\n\n"
        f"<b>{task_title}</b>\n"
        f"Проект: {project_name}\n\n"
        f'<a href="{url}">Открыть задачу</a>'
    )
    if assignee_telegram_id:
        send_notification(assignee_telegram_id, assignee_text)
    if manager_telegram_id and manager_telegram_id != assignee_telegram_id:
        send_notification(manager_telegram_id, manager_text)


def notify_task_status_changed(telegram_id: int, task_title: str,
                                old_status: str, new_status: str,
                                task_uuid: str,
                                manager_telegram_id: int = None) -> None:
    """Уведомить исполнителя и менеджера о смене статуса задачи."""
    url = f"{SITE_URL}/t/{task_uuid}/"
    text = (
        f"🔄 <b>Статус задачи изменён</b>\n\n"
        f"<b>{task_title}</b>\n"
        f"{old_status} → <b>{new_status}</b>\n\n"
        f'<a href="{url}">Открыть задачу</a>'
    )
    recipients = [telegram_id]
    if manager_telegram_id and manager_telegram_id != telegram_id:
        recipients.append(manager_telegram_id)
    _notify_many(recipients, text)


def notify_task_comment(task_title: str, author_name: str, task_uuid: str,
                        assignee_telegram_id: int = None,
                        manager_telegram_id: int = None) -> None:
    """Уведомить исполнителя и менеджера о новом комментарии."""
    url = f"{SITE_URL}/t/{task_uuid}/"
    text = (
        f"💬 <b>Новый комментарий к задаче</b>\n\n"
        f"<b>{task_title}</b>\n"
        f"Автор: {author_name}\n\n"
        f'<a href="{url}">Открыть задачу</a>'
    )
    _notify_many([assignee_telegram_id, manager_telegram_id], text)


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
    send_notification(telegram_id, text)


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
