"""
Роуты аутентификации: вход, выход, пинг сессии, Telegram Login.
"""
import logging
import time

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import REMEMBER_ME_MAX_AGE, SESSION_MAX_AGE, TELEGRAM_BOT_USERNAME, SITE_URL
from app.dependencies import get_db
from app.models.user import User
from app.utils import flash, templates
from app.telegram import (
    validate_telegram_auth, generate_login_code, validate_login_code,
    send_message, answer_callback, notify_managers_registration,
    _inline_kb, _reply_kb,
    get_pending_reg, set_pending_reg, delete_pending_reg,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _login_error(request: Request, error: str) -> HTMLResponse:
    """Ответ с ошибкой для страницы входа через Telegram."""
    return templates.TemplateResponse(
        "accounts/login.html",
        {
            "request": request,
            "error": error,
            "telegram_bot_username": TELEGRAM_BOT_USERNAME,
            "site_url": SITE_URL,
            "show_password_form": False,
        },
    )


@router.get("/accounts/login/", response_class=HTMLResponse, name="login")
async def login_get(request: Request):
    user_id = request.session.get("user_id")
    if user_id:
        return RedirectResponse(url="/p/", status_code=302)
    return templates.TemplateResponse(
        "accounts/login.html",
        {
            "request": request,
            "error": None,
            "reason": request.query_params.get("reason"),
            "telegram_bot_username": TELEGRAM_BOT_USERNAME, "site_url": SITE_URL,
            # admin=1 показывает форму логин/пароль
            "show_password_form": request.query_params.get("admin") == "1",
        },
    )


@router.get("/accounts/telegram-callback/", name="telegram_callback")
async def telegram_callback(request: Request, db: Session = Depends(get_db)):
    """Callback от Telegram Login Widget."""
    data = dict(request.query_params)
    logger.warning("Telegram callback data: %s", {k: v for k, v in data.items() if k != "hash"})

    if not validate_telegram_auth(data):
        return _login_error(request, "Ошибка проверки данных Telegram. Попробуйте ещё раз.")

    telegram_id = int(data.get("id", 0))
    tg_username = data.get("username", "")

    user = db.query(User).filter(User.telegram_id == telegram_id, User.is_active == True).first()

    # Если не нашли по ID — пробуем по telegram_username и привязываем ID
    if not user and tg_username:
        user = db.query(User).filter(
            User.telegram_username == tg_username, User.is_active == True
        ).first()
        if user and user.telegram_id is None:
            user.telegram_id = telegram_id
            db.commit()

    if not user:
        return _login_error(request, "Ваш Telegram-аккаунт не привязан к системе. Обратитесь к менеджеру.")

    request.session["user_id"] = user.id
    request.session["last_activity"] = time.time()
    return RedirectResponse(url="/p/", status_code=302)


@router.post("/accounts/login/", name="login_post")
async def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    remember_me: bool = Form(False),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    if user and user.verify_password(password):
        request.session["user_id"] = user.id
        request.session["last_activity"] = time.time()
        if remember_me:
            request.session["remember_me"] = True
        else:
            request.session.pop("remember_me", None)

        next_url = request.query_params.get("next", "/p/")
        return RedirectResponse(url=next_url, status_code=302)

    return templates.TemplateResponse(
        "accounts/login.html",
        {
            "request": request,
            "error": "Неверный логин или пароль.",
            "username_value": username,
        },
        status_code=200,
    )


@router.get("/accounts/logout/", name="logout")
@router.post("/accounts/logout/")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/accounts/login/", status_code=302)


@router.post("/bot/webhook/", name="bot_webhook", include_in_schema=False)
async def bot_webhook(request: Request, db: Session = Depends(get_db)):
    """Webhook от Telegram Bot."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"ok": True})

    # ── Обработка нажатий inline-кнопок ──────────────────────────────────────
    if "callback_query" in data:
        cq = data["callback_query"]
        cq_id = cq.get("id")
        cq_data = cq.get("data", "")
        from_user = cq.get("from", {})
        telegram_id = from_user.get("id")
        tg_username = from_user.get("username", "")

        if cq_data == "reg_request":
            # Начать заявку на регистрацию
            set_pending_reg(telegram_id, tg_username, "await_name")
            answer_callback(cq_id)
            send_message(telegram_id,
                "📝 Введите ваше имя и фамилию:",
                _reply_kb(["Отмена"], one_time=True))

        elif cq_data == "get_code":
            user = db.query(User).filter(
                User.telegram_id == telegram_id, User.is_active == True
            ).first()
            if user:
                code = generate_login_code(telegram_id)
                answer_callback(cq_id, "Код отправлен!")
                send_message(telegram_id,
                    f"🔑 Ваш код для входа:\n\n<code>{code}</code>\n\n⏱ Действителен 5 минут.",
                    _reply_kb(["🔑 Получить новый код"], ["❓ Помощь"]))
            else:
                answer_callback(cq_id, "Нет доступа")

        elif cq_data == "help":
            answer_callback(cq_id)
            send_message(telegram_id,
                "ℹ️ <b>Справка</b>\n\n"
                "/login — получить код для входа на сайт\n"
                "/start — главное меню\n\n"
                "Если вы не зарегистрированы — нажмите «Подать заявку» "
                "и менеджер добавит вас в систему.")

        return JSONResponse({"ok": True})

    # ── Обработка текстовых сообщений и контактов ────────────────────────────
    message = data.get("message", {})
    if not message:
        return JSONResponse({"ok": True})

    text = message.get("text", "").strip()
    contact = message.get("contact")          # Telegram contact (номер телефона)
    from_user = message.get("from", {})
    chat = message.get("chat", {})
    telegram_id = chat.get("id")
    tg_username = from_user.get("username", "")
    first_name = from_user.get("first_name", "")

    if not telegram_id:
        return JSONResponse({"ok": True})

    # ── Проверяем состояние заявки ────────────────────────────────────────────
    pending = get_pending_reg(telegram_id)

    if pending and pending.step == "await_name":
        if text == "Отмена":
            delete_pending_reg(telegram_id)
            send_message(telegram_id, "Отменено.", _reply_kb(["Подать заявку"], ["❓ Помощь"]))
        else:
            name = text
            delete_pending_reg(telegram_id)
            notify_managers_registration(telegram_id, tg_username, name)
            send_message(telegram_id,
                "✅ Заявка отправлена!\n\n"
                "Менеджер рассмотрит её и добавит вас в систему.\n"
                "После этого напишите /login чтобы войти.",
                _reply_kb(["❓ Помощь"]))
        return JSONResponse({"ok": True})

    # ── Ищем пользователя в системе ──────────────────────────────────────────
    user = db.query(User).filter(
        User.telegram_id == telegram_id, User.is_active == True
    ).first()

    # Если не нашли по ID — пробуем по username и привязываем ID
    if not user and tg_username:
        user = db.query(User).filter(
            User.telegram_username == tg_username, User.is_active == True
        ).first()
        if user and user.telegram_id is None:
            user.telegram_id = telegram_id
            db.commit()

    # ── Команды ──────────────────────────────────────────────────────────────
    if text in ("/start", "/login", "🔑 Получить код для входа"):
        if user:
            code = generate_login_code(telegram_id)
            send_message(telegram_id,
                f"👋 Привет, {user.get_display_name()}!\n\n"
                f"🔑 Ваш код для входа:\n\n<code>{code}</code>\n\n"
                f"⏱ Действителен 5 минут.\n\n"
                f"Введите его на странице входа: {SITE_URL}",
                _reply_kb(["🔑 Получить код для входа"], ["❓ Помощь"]))
        else:
            send_message(telegram_id,
                f"👋 Привет, {first_name or 'пользователь'}!\n\n"
                f"Вы ещё не зарегистрированы в системе.\n"
                f"Нажмите кнопку ниже чтобы подать заявку:",
                _reply_kb(["📝 Подать заявку"], ["❓ Помощь"]))

    elif text == "📝 Подать заявку":
        if user:
            send_message(telegram_id, "Вы уже зарегистрированы!",
                _reply_kb(["🔑 Получить код для входа"], ["❓ Помощь"]))
        else:
            set_pending_reg(telegram_id, tg_username, "await_name")
            send_message(telegram_id,
                "📝 Введите ваше имя и фамилию:",
                _reply_kb(["Отмена"], one_time=True))

    elif text == "❓ Помощь":
        kb = _reply_kb(["🔑 Получить код для входа"], ["❓ Помощь"]) if user else _reply_kb(["📝 Подать заявку"], ["❓ Помощь"])
        send_message(telegram_id,
            "ℹ️ <b>Справка</b>\n\n"
            "🔑 <b>Получить код для входа</b> — войти на сайт\n"
            "📝 <b>Подать заявку</b> — зарегистрироваться\n\n"
            f"Сайт: {SITE_URL}",
            kb)

    return JSONResponse({"ok": True})


@router.post("/accounts/login-by-code/", name="login_by_code")
async def login_by_code(
    request: Request,
    code: str = Form(...),
    db: Session = Depends(get_db),
):
    """Вход по коду из Telegram-бота."""
    telegram_id = validate_login_code(code.strip())
    if not telegram_id:
        return _login_error(request, "Неверный или истёкший код. Отправьте /login боту снова.")

    user = db.query(User).filter(User.telegram_id == telegram_id, User.is_active == True).first()
    if not user:
        return _login_error(request, "Аккаунт не найден.")

    request.session["user_id"] = user.id
    request.session["last_activity"] = time.time()
    return RedirectResponse(url="/p/", status_code=302)


@router.post("/session/ping/", name="session_ping")
async def session_ping(request: Request):
    if request.session.get("user_id"):
        request.session["last_activity"] = time.time()
    return JSONResponse({"ok": True})
