"""
Точка входа FastAPI-приложения (замена task_tracker/wsgi.py + urls.py).
"""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import SECRET_KEY, STATIC_DIR, MEDIA_DIR, DEBUG
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


# ── Обработчики ошибок ────────────────────────────────────────────────────────
from app.utils import templates


@app.exception_handler(403)
async def forbidden_handler(request: Request, exc):
    user_id = request.session.get("user_id")
    if not user_id:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/accounts/login/", status_code=302)
    from app.database import SessionLocal
    from app.models.user import User
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()
    return templates.TemplateResponse(
        "403.html" if (STATIC_DIR.parent / "templates" / "403.html").exists() else "base.html",
        {"request": request, "user": user},
        status_code=403,
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return HTMLResponse("<h1>404 — Страница не найдена</h1>", status_code=404)
