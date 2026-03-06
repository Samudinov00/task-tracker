"""
Роуты уведомлений (аналог соответствующих views в projects/views.py).
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.dependencies import get_db, require_auth
from app.models.project import Notification, Task
from app.utils import templates

router = APIRouter()


@router.get("/notifications/", response_class=HTMLResponse, name="notifications")
async def notifications_list(request: Request, db: Session = Depends(get_db)):
    user = require_auth(request, db)
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .options(joinedload(Notification.task).joinedload(Task.project))
        .order_by(Notification.created_at.desc())
        .all()
    )
    # Помечаем как прочитанные
    db.query(Notification).filter(
        Notification.user_id == user.id, Notification.is_read == False
    ).update({"is_read": True})
    db.commit()

    return templates.TemplateResponse(
        "projects/notifications.html",
        {"request": request, "user": user, "notifications": notifications, "unread_notifications_count": 0},
    )


@router.get("/notifications/count/", name="notifications_count")
async def notifications_count_api(request: Request, db: Session = Depends(get_db)):
    user = require_auth(request, db)
    count = db.query(Notification).filter(
        Notification.user_id == user.id, Notification.is_read == False
    ).count()
    return JSONResponse({"count": count})


@router.get("/notifications/recent/", name="notifications_recent")
async def notifications_recent_api(request: Request, db: Session = Depends(get_db)):
    user = require_auth(request, db)
    items = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.is_read == False)
        .options(joinedload(Notification.task))
        .order_by(Notification.created_at.desc())
        .limit(6)
        .all()
    )
    data = []
    for n in items:
        data.append({
            "id": n.id,
            "message": n.message,
            "created_at": n.created_at.strftime("%d.%m %H:%M"),
            "task_id": n.task_id,
            "task_url": f"/t/{n.task.uuid}/" if n.task else None,
        })
    total = db.query(Notification).filter(
        Notification.user_id == user.id, Notification.is_read == False
    ).count()
    return JSONResponse({"notifications": data, "count": total})


@router.post("/notifications/mark-all-read/", name="notifications_mark_all_read")
async def notifications_mark_all_read(request: Request, db: Session = Depends(get_db)):
    user = require_auth(request, db)
    db.query(Notification).filter(
        Notification.user_id == user.id, Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return JSONResponse({"success": True})
