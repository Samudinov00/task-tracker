"""
Middleware для сброса сессии при бездействии (аналог task_tracker/middleware.py).
"""
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.config import INACTIVITY_TIMEOUT

_POLLING_PATHS = frozenset([
    "/notifications/count/",
    "/notifications/recent/",
    "/notifications/mark-all-read/",
])


def _is_polling_path(path: str) -> bool:
    if path in _POLLING_PATHS:
        return True
    if path.startswith("/p/") and path.endswith("/kanban-state/"):
        return True
    return False


class SessionInactivityMiddleware(BaseHTTPMiddleware):
    """Выбрасывает пользователя после 30 минут бездействия."""

    async def dispatch(self, request: Request, call_next):
        user_id = request.session.get("user_id")
        if user_id and not request.session.get("remember_me"):
            now = time.time()
            last = request.session.get("last_activity")

            if last and (now - last) > INACTIVITY_TIMEOUT:
                request.session.clear()
                return RedirectResponse(
                    url="/accounts/login/?reason=timeout",
                    status_code=302,
                )

            if not _is_polling_path(request.url.path):
                request.session["last_activity"] = now

        return await call_next(request)
