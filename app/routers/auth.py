"""
Роуты аутентификации: вход, выход, пинг сессии, Telegram Login.
"""
import time

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import REMEMBER_ME_MAX_AGE, SESSION_MAX_AGE, TELEGRAM_BOT_USERNAME
from app.database import SessionLocal
from app.models.user import User
from app.utils import flash, templates
from app.telegram import validate_telegram_auth

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
            "telegram_bot_username": TELEGRAM_BOT_USERNAME,
            # admin=1 показывает форму логин/пароль
            "show_password_form": request.query_params.get("admin") == "1",
        },
    )


@router.get("/accounts/telegram-callback/", name="telegram_callback")
async def telegram_callback(request: Request, db: Session = Depends(get_db)):
    """Callback от Telegram Login Widget."""
    data = dict(request.query_params)

    if not validate_telegram_auth(data):
        return templates.TemplateResponse(
            "accounts/login.html",
            {
                "request": request,
                "error": "Ошибка проверки данных Telegram. Попробуйте ещё раз.",
                "telegram_bot_username": TELEGRAM_BOT_USERNAME,
                "show_password_form": False,
            },
        )

    telegram_id = int(data.get("id", 0))
    user = db.query(User).filter(User.telegram_id == telegram_id, User.is_active == True).first()

    if not user:
        return templates.TemplateResponse(
            "accounts/login.html",
            {
                "request": request,
                "error": "Ваш Telegram-аккаунт не привязан к системе. Обратитесь к менеджеру.",
                "telegram_bot_username": TELEGRAM_BOT_USERNAME,
                "show_password_form": False,
            },
        )

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


@router.post("/session/ping/", name="session_ping")
async def session_ping(request: Request):
    from fastapi.responses import JSONResponse
    if request.session.get("user_id"):
        request.session["last_activity"] = time.time()
    return JSONResponse({"ok": True})
