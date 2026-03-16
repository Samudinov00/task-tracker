"""
Точка входа FastAPI-приложения (замена task_tracker/wsgi.py + urls.py).
"""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import SECRET_KEY, STATIC_DIR, MEDIA_DIR, DEBUG, TELEGRAM_BOT_TOKEN, SITE_URL
from app.middleware import SessionInactivityMiddleware
from app.routers import auth, accounts, projects, notifications, analytics

app = FastAPI(
    title="Task Tracker",
    description="Система управления задачами",
    debug=DEBUG,
)

# ── Middleware ────────────────────────────────────────────────────────────────
# Порядок add_middleware — LIFO: последний добавленный выполняется первым.
# SessionInactivityMiddleware должна работать ПОСЛЕ SessionMiddleware,
# поэтому добавляем её ПЕРВОЙ.
app.add_middleware(SessionInactivityMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="session",
    max_age=86400,          # 24 ч
    same_site="lax",
    https_only=False,       # True в production за nginx
)

# ── Статика и медиа ───────────────────────────────────────────────────────────
STATIC_DIR.mkdir(exist_ok=True)
MEDIA_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

# ── Роутеры ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(projects.router)
app.include_router(notifications.router)
app.include_router(analytics.router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health/", include_in_schema=False)
async def health():
    return JSONResponse({"status": "ok"})


# ── Регистрация Telegram webhook при старте ───────────────────────────────────
@app.on_event("startup")
async def register_telegram_webhook():
    if not TELEGRAM_BOT_TOKEN:
        return
    import httpx
    webhook_url = f"{SITE_URL}/bot/webhook/"
    try:
        httpx.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook",
            json={"url": webhook_url},
            timeout=5,
        )
    except Exception:
        pass


# ── Обработчики ошибок ────────────────────────────────────────────────────────
from app.utils import templates


def _get_user(request: Request):
    from app.database import SessionLocal
    from app.models.user import User
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()


def _error_response(request: Request, code: int, title: str, message: str):
    user = _get_user(request)
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "user": user,
            "error_code": code,
            "error_title": title,
            "error_message": message,
        },
        status_code=code,
    )


@app.exception_handler(400)
async def bad_request_handler(request: Request, exc):
    return _error_response(request, 400, "Некорректный запрос",
        "Запрос содержит ошибку. Проверьте введённые данные и попробуйте снова.")


@app.exception_handler(403)
async def forbidden_handler(request: Request, exc):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/accounts/login/", status_code=302)
    return _error_response(request, 403, "Доступ запрещён",
        "У вас недостаточно прав для просмотра этой страницы.")


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return _error_response(request, 404, "Страница не найдена",
        "Запрашиваемая страница не существует или была удалена.")


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    return _error_response(request, 500, "Ошибка сервера",
        "Что-то пошло не так на нашей стороне. Попробуйте обновить страницу или зайдите позже.")


_logger = logging.getLogger(__name__)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc):
    _logger.exception("Unhandled exception: %s", exc)
    return _error_response(request, 500, "Ошибка сервера",
        "Что-то пошло не так на нашей стороне. Попробуйте обновить страницу или зайдите позже.")
