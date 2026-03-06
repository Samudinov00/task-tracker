"""
Общие зависимости FastAPI: сессия БД, текущий пользователь, проверки доступа.
"""
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.user import User


# ── Сессия БД ────────────────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Текущий пользователь ──────────────────────────────────────────────────────
def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Возвращает пользователя из сессии или None."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id, User.is_active == True).first()


def require_auth(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Требует аутентификации; редиректит на /accounts/login/ при отсутствии."""
    user = get_current_user(request, db)
    if user is None:
        from fastapi.responses import RedirectResponse
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/accounts/login/"},
        )
    return user


def require_manager(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Требует роли «менеджер»."""
    user = require_auth(request, db)
    if not user.is_manager():
        raise HTTPException(status_code=403, detail="Доступ запрещён. Требуются права менеджера.")
    return user
