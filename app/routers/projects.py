"""
Роуты проектов и задач (аналог projects/views.py).
"""
import csv
import io
import json
import uuid as uuid_lib
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload, selectinload
from typing import List, Optional

from app.database import SessionLocal
from app.dependencies import get_db, get_unread_count, require_auth, require_manager
from app.models.project import (
    Comment, Notification, Project, ProjectStatus, Task,
    TaskChangeLog, TaskStatusLog,
    DEFAULT_STATUSES, STATUS_COLOR_CHOICES, PRIORITY_CHOICES,
    TYPE_TASK_ASSIGNED, TYPE_TASK_STATUS, TYPE_COMMENT,
)
from app.models.user import User, ROLE_EXECUTOR, ROLE_CLIENT
from app.utils import flash, templates
from app import telegram as tg

router = APIRouter()


# ── Хелперы ──────────────────────────────────────────────────────────────────

def _check_project_access(user: User, project: Project, db: Session) -> None:
    if user.is_manager():
        if project.manager_id != user.id:
            raise HTTPException(status_code=403, detail="Нет доступа к этому проекту.")
    elif user.is_client():
        ids = [c.id for c in project.clients]
        if user.id not in ids:
            raise HTTPException(status_code=403, detail="Нет доступа к этому проекту.")
    elif user.is_executor():
        in_team = user.id in [e.id for e in project.executors]
        has_task = db.query(Task).filter(Task.project_id == project.id, Task.assignee_id == user.id).first() is not None
        if not (in_team or has_task):
            raise HTTPException(status_code=403, detail="Нет доступа к этому проекту.")


def _notify(db: Session, user_ids: list, task_id: int, ntype: str, message: str) -> None:
    try:
        from app.tasks.notifications import send_notifications
        send_notifications.delay(user_ids, task_id, ntype, message)
    except Exception:
        pass


def _get_project_by_uuid(db: Session, uuid_str) -> Project:
    project = db.query(Project).filter(Project.uuid == uuid_str).first()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return project


def _get_task_by_uuid(db: Session, uuid_str) -> Task:
    task = db.query(Task).filter(Task.uuid == uuid_str).first()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена.")
    return task


def _get_manager_tg(db: Session, manager_id: int, acting_user_id: int) -> int | None:
    """Telegram ID менеджера проекта, если он не является текущим пользователем."""
    if manager_id == acting_user_id:
        return None
    manager = db.query(User).filter(User.id == manager_id).first()
    return manager.telegram_id if manager else None


def _notify_status_change(
    db: Session, task: Task, user: "User",
    old_status_name: str, new_status_name: str,
) -> None:
    """Создаёт TaskStatusLog, уведомление в БД и Telegram при смене статуса."""
    db.add(TaskStatusLog(
        task_id=task.id, changed_by_id=user.id,
        old_status=old_status_name, new_status=new_status_name,
    ))
    recipients = set()
    if task.assignee_id and task.assignee_id != user.id:
        recipients.add(task.assignee_id)
    if task.project.manager_id != user.id:
        recipients.add(task.project.manager_id)
    _notify(db, list(recipients), task.id, TYPE_TASK_STATUS,
            f"Статус задачи «{task.title}» изменён на «{new_status_name}»")
    assignee_tg = task.assignee.telegram_id if task.assignee and task.assignee_id != user.id else None
    manager_tg = _get_manager_tg(db, task.project.manager_id, user.id)
    if assignee_tg or manager_tg:
        tg.notify_task_status_changed(
            assignee_tg, task.title, old_status_name, new_status_name, str(task.uuid), manager_tg,
        )


def _create_default_statuses(db: Session, project: Project) -> None:
    for s in DEFAULT_STATUSES:
        status = ProjectStatus(
            project_id=project.id,
            name=s["name"],
            color=s["color"],
            order=s["order"],
            is_final=s["is_final"],
        )
        db.add(status)
    db.commit()


# ── Проекты ──────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse, name="home")
async def home(request: Request, db: Session = Depends(get_db)):
    user = require_auth(request, db)

    if user.is_manager():
        projects = (
            db.query(Project)
            .filter(Project.manager_id == user.id)
            .options(selectinload(Project.tasks).joinedload(Task.status_obj), selectinload(Project.statuses))
            .order_by(Project.created_at.desc())
            .all()
        )
    elif user.is_client():
        projects = (
            db.query(Project)
            .filter(Project.clients.any(User.id == user.id))
            .options(selectinload(Project.tasks).joinedload(Task.status_obj), selectinload(Project.statuses))
            .all()
        )
    else:
        projects = (
            db.query(Project)
            .filter(
                or_(
                    Project.executors.any(User.id == user.id),
                    Project.tasks.any(Task.assignee_id == user.id),
                )
            )
            .distinct()
            .options(selectinload(Project.tasks).joinedload(Task.status_obj), selectinload(Project.statuses))
            .all()
        )

    all_project_ids = [p.id for p in projects]
    today = date.today()

    # Recent tasks (last 8, assigned to user or in manager's projects)
    recent_qs = (
        db.query(Task)
        .filter(Task.project_id.in_(all_project_ids))
        .options(joinedload(Task.project), joinedload(Task.status_obj))
        .order_by(Task.updated_at.desc())
    )
    if user.is_executor():
        recent_qs = recent_qs.filter(Task.assignee_id == user.id)
    recent_tasks = recent_qs.limit(8).all()

    # Aggregate stats
    all_tasks_flat = [t for p in projects for t in p.tasks]
    total_projects = len(projects)
    total_tasks = len(all_tasks_flat)
    production_count = sum(1 for t in all_tasks_flat if t.status_obj and t.status_obj.is_final)
    overdue_count = sum(
        1 for t in all_tasks_flat
        if t.deadline and t.deadline < today and not (t.status_obj and t.status_obj.is_final)
    )

    # Status summary — aggregate across all projects
    status_map: dict = {}
    for p in projects:
        for s in p.statuses:
            key = s.name
            if key not in status_map:
                status_map[key] = {"label": s.name, "badge": s.color, "count": 0}
            status_map[key]["count"] += sum(1 for t in p.tasks if t.status_id == s.id)
    statuses = [v for v in status_map.values() if v["count"] > 0]

    unread_count = get_unread_count(db, user.id)
    return templates.TemplateResponse(
        "projects/dashboard.html",
        {
            "request": request, "user": user,
            "total_projects": total_projects,
            "total_tasks": total_tasks,
            "production_count": production_count,
            "overdue_count": overdue_count,
            "statuses": statuses,
            "recent_tasks": recent_tasks,
            "projects": projects,
            "unread_notifications_count": unread_count,
        },
    )


@router.get("/p/", response_class=HTMLResponse, name="project_list")
async def project_list(request: Request, db: Session = Depends(get_db)):
    user = require_auth(request, db)
    if user.is_manager():
        projects = db.query(Project).filter(Project.manager_id == user.id).order_by(Project.created_at.desc()).all()
    elif user.is_client():
        projects = user.client_projects
    else:  # executor
        projects = (
            db.query(Project)
            .filter(
                or_(
                    Project.executors.any(User.id == user.id),
                    Project.tasks.any(Task.assignee_id == user.id),
                )
            )
            .distinct()
            .order_by(Project.created_at.desc())
            .all()
        )
    unread_count = get_unread_count(db, user.id)
    return templates.TemplateResponse(
        "projects/project_list.html",
        {"request": request, "user": user, "projects": projects, "unread_notifications_count": unread_count},
    )


@router.get("/p/create/", response_class=HTMLResponse, name="project_create")
async def project_create_get(request: Request, db: Session = Depends(get_db)):
    user = require_manager(request, db)
    executors = db.query(User).filter(User.role == ROLE_EXECUTOR).all()
    clients = db.query(User).filter(User.role == ROLE_CLIENT).all()
    return templates.TemplateResponse(
        "projects/project_form.html",
        {
            "request": request, "user": user, "title": "Новый проект",
            "project": None, "all_executors": executors, "all_clients": clients,
            "selected_executor_ids": [], "selected_client_ids": [], "errors": {},
            "status_color_choices": STATUS_COLOR_CHOICES,
        },
    )


@router.post("/p/create/", name="project_create_post")
async def project_create_post(
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_manager(request, db)
    form = await request.form()
    name = form.get("name", "").strip()
    description = form.get("description", "").strip()
    executor_ids = [int(x) for x in form.getlist("executors") if x.isdigit()]
    client_ids = [int(x) for x in form.getlist("clients") if x.isdigit()]

    errors = {}
    if not name:
        errors["name"] = "Название обязательно."

    if errors:
        executors = db.query(User).filter(User.role == ROLE_EXECUTOR).all()
        clients = db.query(User).filter(User.role == ROLE_CLIENT).all()
        return templates.TemplateResponse(
            "projects/project_form.html",
            {
                "request": request, "user": user, "title": "Новый проект",
                "project": None, "all_executors": executors, "all_clients": clients,
                "selected_executor_ids": executor_ids, "selected_client_ids": client_ids,
                "errors": errors, "form_data": {"name": name, "description": description},
                "status_color_choices": STATUS_COLOR_CHOICES,
            },
        )

    project = Project(name=name, description=description, manager_id=user.id)
    db.add(project)
    db.flush()  # get project.id

    if executor_ids:
        execs = db.query(User).filter(User.id.in_(executor_ids)).all()
        project.executors = execs
    if client_ids:
        cls = db.query(User).filter(User.id.in_(client_ids)).all()
        project.clients = cls

    db.commit()
    db.refresh(project)
    _create_default_statuses(db, project)

    flash(request, f"Проект «{name}» создан.", "success")
    return RedirectResponse(url=f"/p/{project.uuid}/board/", status_code=302)


@router.get("/p/{uuid}/", response_class=HTMLResponse, name="project_detail")
async def project_detail(request: Request, uuid: uuid_lib.UUID, db: Session = Depends(get_db)):
    user = require_auth(request, db)
    project = _get_project_by_uuid(db, uuid)
    _check_project_access(user, project, db)

    tasks_q = db.query(Task).filter(Task.project_id == project.id).options(
        joinedload(Task.assignee), joinedload(Task.status_obj)
    )
    if user.is_executor():
        tasks_q = tasks_q.filter(Task.assignee_id == user.id)
    elif user.is_client():
        tasks_q = tasks_q.filter(Task.clients.any(User.id == user.id))

    tasks = tasks_q.all()
    done_count = sum(1 for t in tasks if t.status_obj and t.status_obj.is_final)
    in_work_count = len(tasks) - done_count
    unread_count = get_unread_count(db, user.id)
    return templates.TemplateResponse(
        "projects/project_detail.html",
        {
            "request": request, "user": user, "project": project, "tasks": tasks,
            "in_work_count": in_work_count,
            "done_count": done_count,
            "unread_notifications_count": unread_count,
        },
    )


@router.get("/p/{uuid}/edit/", response_class=HTMLResponse, name="project_edit")
async def project_edit_get(request: Request, uuid: uuid_lib.UUID, db: Session = Depends(get_db)):
    user = require_manager(request, db)
    project = _get_project_by_uuid(db, uuid)
    if project.manager_id != user.id:
        raise HTTPException(status_code=403)
    all_executors = db.query(User).filter(User.role == ROLE_EXECUTOR).all()
    all_clients = db.query(User).filter(User.role == ROLE_CLIENT).all()
    return templates.TemplateResponse(
        "projects/project_form.html",
        {
            "request": request, "user": user, "title": "Редактировать проект",
            "project": project, "all_executors": all_executors, "all_clients": all_clients,
            "selected_executor_ids": [e.id for e in project.executors],
            "selected_client_ids": [c.id for c in project.clients],
            "errors": {},
            "status_color_choices": STATUS_COLOR_CHOICES,
        },
    )


@router.post("/p/{uuid}/edit/", name="project_edit_post")
async def project_edit_post(request: Request, uuid: uuid_lib.UUID, db: Session = Depends(get_db)):
    user = require_manager(request, db)
    project = _get_project_by_uuid(db, uuid)
    if project.manager_id != user.id:
        raise HTTPException(status_code=403)

    form = await request.form()
    name = form.get("name", "").strip()
    description = form.get("description", "").strip()
    executor_ids = [int(x) for x in form.getlist("executors") if x.isdigit()]
    client_ids = [int(x) for x in form.getlist("clients") if x.isdigit()]

    errors = {}
    if not name:
        errors["name"] = "Название обязательно."

    if errors:
        all_executors = db.query(User).filter(User.role == ROLE_EXECUTOR).all()
        all_clients = db.query(User).filter(User.role == ROLE_CLIENT).all()
        return templates.TemplateResponse(
            "projects/project_form.html",
            {
                "request": request, "user": user, "title": "Редактировать проект",
                "project": project, "all_executors": all_executors, "all_clients": all_clients,
                "selected_executor_ids": executor_ids, "selected_client_ids": client_ids,
                "errors": errors,
                "status_color_choices": STATUS_COLOR_CHOICES,
            },
        )

    project.name = name
    project.description = description
    project.executors = db.query(User).filter(User.id.in_(executor_ids)).all() if executor_ids else []
    project.clients = db.query(User).filter(User.id.in_(client_ids)).all() if client_ids else []
    db.commit()
    flash(request, "Проект обновлён.", "success")
    return RedirectResponse(url=f"/p/{project.uuid}/", status_code=302)


@router.get("/p/{uuid}/delete/", response_class=HTMLResponse, name="project_delete")
async def project_delete_get(request: Request, uuid: uuid_lib.UUID, db: Session = Depends(get_db)):
    user = require_manager(request, db)
    project = _get_project_by_uuid(db, uuid)
    if project.manager_id != user.id:
        raise HTTPException(status_code=403)
    unread_count = get_unread_count(db, user.id)
    return templates.TemplateResponse(
        "projects/project_confirm_delete.html",
        {"request": request, "user": user, "project": project, "unread_notifications_count": unread_count},
    )


@router.post("/p/{uuid}/delete/", name="project_delete_post")
async def project_delete_post(request: Request, uuid: uuid_lib.UUID, db: Session = Depends(get_db)):
    user = require_manager(request, db)
    project = _get_project_by_uuid(db, uuid)
    if project.manager_id != user.id:
        raise HTTPException(status_code=403)

    task_count = db.query(Task).filter(Task.project_id == project.id).count()
    if task_count > 0:
        flash(request, "Нельзя удалить проект, в котором есть задачи.", "danger")
        return RedirectResponse(url="/p/", status_code=302)

    db.delete(project)
    db.commit()
    flash(request, "Проект удалён.", "success")
    return RedirectResponse(url="/p/", status_code=302)


# ── Статусы проекта (управление) ─────────────────────────────────────────────

@router.post("/p/{uuid}/statuses/add/", name="project_status_add")
async def project_status_add(request: Request, uuid: uuid_lib.UUID, db: Session = Depends(get_db)):
    user = require_manager(request, db)
    project = _get_project_by_uuid(db, uuid)
    if project.manager_id != user.id:
        raise HTTPException(status_code=403)

    form = await request.form()
    name = form.get("name", "").strip()
    color = form.get("color", "primary")
    is_final = form.get("is_final") == "on"

    if not name:
        flash(request, "Название статуса обязательно.", "danger")
        return RedirectResponse(url=f"/p/{project.uuid}/edit/", status_code=302)

    max_order = max((s.order for s in project.statuses), default=-1) + 1
    status = ProjectStatus(
        project_id=project.id,
        name=name,
        color=color,
        order=max_order,
        is_final=is_final,
    )
    db.add(status)
    db.commit()
    flash(request, f"Статус «{name}» добавлен.", "success")
    return RedirectResponse(url=f"/p/{project.uuid}/edit/", status_code=302)


@router.post("/p/{uuid}/statuses/{sid}/delete/", name="project_status_delete")
async def project_status_delete(
    request: Request, uuid: uuid_lib.UUID, sid: int, db: Session = Depends(get_db)
):
    user = require_manager(request, db)
    project = _get_project_by_uuid(db, uuid)
    if project.manager_id != user.id:
        raise HTTPException(status_code=403)

    status = db.query(ProjectStatus).filter(
        ProjectStatus.id == sid, ProjectStatus.project_id == project.id
    ).first()
    if not status:
        raise HTTPException(status_code=404, detail="Статус не найден.")

    task_count = db.query(Task).filter(Task.status_id == sid).count()
    if task_count > 0:
        flash(request, f"Нельзя удалить статус «{status.name}»: есть задачи в этом статусе.", "danger")
        return RedirectResponse(url=f"/p/{project.uuid}/edit/", status_code=302)

    db.delete(status)
    db.commit()
    flash(request, f"Статус «{status.name}» удалён.", "success")
    return RedirectResponse(url=f"/p/{project.uuid}/edit/", status_code=302)


@router.post("/p/{uuid}/statuses/reorder/", name="project_status_reorder")
async def project_status_reorder(
    request: Request, uuid: uuid_lib.UUID, db: Session = Depends(get_db)
):
    user = require_manager(request, db)
    project = _get_project_by_uuid(db, uuid)
    if project.manager_id != user.id:
        raise HTTPException(status_code=403)

    data = await request.json()
    ids = data.get("ids", [])
    for idx, sid in enumerate(ids):
        db.query(ProjectStatus).filter(
            ProjectStatus.id == int(sid), ProjectStatus.project_id == project.id
        ).update({"order": idx})
    db.commit()
    return JSONResponse({"success": True})


# ── Канбан-доска ──────────────────────────────────────────────────────────────

@router.get("/p/{project_uuid}/board/", response_class=HTMLResponse, name="kanban")
async def kanban(request: Request, project_uuid: uuid_lib.UUID, db: Session = Depends(get_db)):
    user = require_auth(request, db)
    project = (
        db.query(Project)
        .filter(Project.uuid == project_uuid)
        .options(selectinload(Project.statuses))
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден.")
    _check_project_access(user, project, db)

    final_status_ids = [s.id for s in project.statuses if s.is_final]

    qs = db.query(Task).filter(Task.project_id == project.id).options(
        joinedload(Task.assignee),
        joinedload(Task.comments),
        joinedload(Task.status_obj),
    )
    if user.is_executor():
        qs = qs.filter(Task.assignee_id == user.id)
    elif user.is_client():
        qs = qs.filter(Task.clients.any(User.id == user.id))

    assignee_filter = None
    priority_filter = None
    deadline_filter = None
    executors = []

    if user.is_manager():
        executors = (
            db.query(User)
            .join(Task, Task.assignee_id == User.id)
            .filter(Task.project_id == project.id)
            .distinct()
            .order_by(User.first_name, User.username)
            .all()
        )
        assignee_id = request.query_params.get("assignee")
        if assignee_id == "none":
            qs = qs.filter(Task.assignee_id == None)
            assignee_filter = "none"
        elif assignee_id and assignee_id.isdigit():
            qs = qs.filter(Task.assignee_id == int(assignee_id))
            assignee_filter = assignee_id

    priority = request.query_params.get("priority")
    valid_priorities = [c[0] for c in PRIORITY_CHOICES]
    if priority in valid_priorities:
        qs = qs.filter(Task.priority == priority)
        priority_filter = priority

    deadline = request.query_params.get("deadline")
    today = date.today()
    if deadline == "overdue":
        if final_status_ids:
            qs = qs.filter(Task.deadline < today).filter(~Task.status_id.in_(final_status_ids))
        else:
            qs = qs.filter(Task.deadline < today)
        deadline_filter = "overdue"
    elif deadline == "soon":
        if final_status_ids:
            qs = qs.filter(Task.deadline >= today, Task.deadline <= today + timedelta(days=7)).filter(
                ~Task.status_id.in_(final_status_ids)
            )
        else:
            qs = qs.filter(Task.deadline >= today, Task.deadline <= today + timedelta(days=7))
        deadline_filter = "soon"

    all_tasks = qs.all()

    kanban_columns = [
        {
            "key": str(s.id),
            "label": s.name,
            "color": s.color,
            "icon": s.get_icon(),
            "tasks": sorted(
                [t for t in all_tasks if t.status_id == s.id],
                key=lambda t: t.order,
            ),
        }
        for s in project.statuses
    ]

    unread_count = get_unread_count(db, user.id)
    return templates.TemplateResponse(
        "projects/kanban.html",
        {
            "request": request, "user": user, "project": project,
            "kanban_columns": kanban_columns, "executors": executors,
            "assignee_filter": assignee_filter, "priority_filter": priority_filter,
            "deadline_filter": deadline_filter,
            "priority_choices": PRIORITY_CHOICES,
            "unread_notifications_count": unread_count,
            "today": today,
        },
    )


@router.post("/t/{task_uuid}/move/", name="task_move")
async def task_move(request: Request, task_uuid: uuid_lib.UUID, db: Session = Depends(get_db)):
    user = require_auth(request, db)
    task = _get_task_by_uuid(db, task_uuid)

    if user.is_client():
        return JSONResponse({"error": "Нет доступа"}, status_code=403)
    if user.is_executor() and task.assignee_id != user.id:
        return JSONResponse({"error": "Нет доступа"}, status_code=403)
    if user.is_manager() and task.project.manager_id != user.id:
        return JSONResponse({"error": "Нет доступа"}, status_code=403)

    data = await request.json()
    new_status_str = data.get("status")
    column_ids = data.get("column_ids", [])

    try:
        new_status_id = int(new_status_str)
    except (TypeError, ValueError):
        return JSONResponse({"error": "Неверный статус"}, status_code=400)

    # Validate that the status belongs to this project
    project_statuses = db.query(ProjectStatus).filter(
        ProjectStatus.project_id == task.project_id
    ).all()
    valid_ids = {s.id: s for s in project_statuses}
    if new_status_id not in valid_ids:
        return JSONResponse({"error": "Неверный статус"}, status_code=400)

    old_status_name = task.status_obj.name if task.status_obj else ""
    new_status_name = valid_ids[new_status_id].name

    task.status_id = new_status_id

    for idx, tuuid_str in enumerate(column_ids):
        try:
            tuuid = uuid_lib.UUID(str(tuuid_str))
            db.query(Task).filter(Task.uuid == tuuid, Task.project_id == task.project_id).update({"order": idx})
        except Exception:
            pass

    if old_status_name != new_status_name:
        _notify_status_change(db, task, user, old_status_name, new_status_name)

    db.commit()
    return JSONResponse({"success": True})


@router.get("/p/{project_uuid}/kanban-state/", name="kanban_state")
async def kanban_state_api(request: Request, project_uuid: uuid_lib.UUID, db: Session = Depends(get_db)):
    user = require_auth(request, db)
    project = _get_project_by_uuid(db, project_uuid)
    _check_project_access(user, project, db)

    qs = db.query(Task).filter(Task.project_id == project.id).options(
        joinedload(Task.assignee), joinedload(Task.status_obj), selectinload(Task.comments)
    )
    if user.is_executor():
        qs = qs.filter(Task.assignee_id == user.id)
    elif user.is_client():
        qs = qs.filter(Task.clients.any(User.id == user.id))

    tasks_data = []
    for task in qs.all():
        tasks_data.append({
            "uuid": str(task.uuid),
            "title": task.title,
            "status": str(task.status_id) if task.status_id else "",
            "priority": task.priority,
            "assignee_name": task.assignee.get_display_name() if task.assignee else "",
            "deadline": task.deadline.isoformat() if task.deadline else None,
            "is_overdue": task.is_overdue(),
            "comment_count": len(task.comments),
        })

    return JSONResponse({"tasks": tasks_data, "updated_at": datetime.utcnow().isoformat()})


# ── Задачи ────────────────────────────────────────────────────────────────────

@router.get("/t/{uuid}/", response_class=HTMLResponse, name="task_detail")
async def task_detail(request: Request, uuid: uuid_lib.UUID, db: Session = Depends(get_db)):
    user = require_auth(request, db)
    task = (
        db.query(Task)
        .filter(Task.uuid == uuid)
        .options(
            joinedload(Task.assignee),
            joinedload(Task.project),
            joinedload(Task.created_by),
            joinedload(Task.status_obj),
            selectinload(Task.comments).joinedload(Comment.author),
            selectinload(Task.change_logs).joinedload(TaskChangeLog.changed_by),
            selectinload(Task.status_logs).joinedload(TaskStatusLog.changed_by),
        )
        .first()
    )
    if not task:
        raise HTTPException(status_code=404)
    _check_project_access(user, task.project, db)

    if user.is_executor() and task.assignee_id != user.id:
        raise HTTPException(status_code=403)
    if user.is_client():
        client_ids = [c.id for c in task.clients]
        if user.id not in client_ids:
            raise HTTPException(status_code=403)

    can_edit = user.is_manager() or (user.is_executor() and task.assignee_id == user.id)

    # История изменений
    history = []
    for log in task.status_logs:
        history.append({
            "type": "status",
            "changed_by": log.changed_by,
            "field_name": "Статус",
            "old_value": log.old_status,
            "new_value": log.new_status,
            "changed_at": log.changed_at,
        })
    for log in task.change_logs:
        history.append({
            "type": "field",
            "changed_by": log.changed_by,
            "field_name": log.field_name,
            "old_value": log.old_value,
            "new_value": log.new_value,
            "changed_at": log.changed_at,
        })
    history.sort(key=lambda x: x["changed_at"], reverse=True)

    unread_count = get_unread_count(db, user.id)
    return templates.TemplateResponse(
        "projects/task_detail.html",
        {
            "request": request, "user": user, "task": task,
            "can_edit": can_edit,
            "history": history,
            "unread_notifications_count": unread_count,
        },
    )


@router.post("/t/{uuid}/comment/", name="task_comment_post")
async def task_comment_post(
    request: Request,
    uuid: uuid_lib.UUID,
    db: Session = Depends(get_db),
    text: str = Form(...),
):
    user = require_auth(request, db)
    task = _get_task_by_uuid(db, uuid)
    _check_project_access(user, task.project, db)

    if not text.strip():
        flash(request, "Текст комментария не может быть пустым.", "danger")
        return RedirectResponse(url=f"/t/{task.uuid}/", status_code=302)

    comment = Comment(task_id=task.id, author_id=user.id, text=text.strip())
    db.add(comment)
    db.commit()

    recipients = set()
    if task.assignee_id and task.assignee_id != user.id:
        recipients.add(task.assignee_id)
    if task.project.manager_id != user.id:
        recipients.add(task.project.manager_id)
    _notify(db, list(recipients), task.id, TYPE_COMMENT, f"{user.get_display_name()} прокомментировал задачу «{task.title}»")

    assignee_tg = task.assignee.telegram_id if task.assignee and task.assignee_id != user.id else None
    manager = db.query(User).filter(User.id == task.project.manager_id).first()
    manager_tg = manager.telegram_id if manager and task.project.manager_id != user.id else None
    if assignee_tg or manager_tg:
        tg.notify_task_comment(task.title, user.get_display_name(), str(task.uuid), assignee_tg, manager_tg)

    flash(request, "Комментарий добавлен.", "success")
    return RedirectResponse(url=f"/t/{task.uuid}/", status_code=302)


@router.get("/p/{project_uuid}/new/", response_class=HTMLResponse, name="task_create")
async def task_create_get(request: Request, project_uuid: uuid_lib.UUID, db: Session = Depends(get_db)):
    user = require_manager(request, db)
    project = _get_project_by_uuid(db, project_uuid)
    if project.manager_id != user.id:
        raise HTTPException(status_code=403)

    assignees = list(project.executors) + [user]
    task_clients_list = list(project.clients)
    unread_count = get_unread_count(db, user.id)
    return templates.TemplateResponse(
        "projects/task_form.html",
        {
            "request": request, "user": user, "project": project,
            "title": "Новая задача", "task": None,
            "assignees": assignees, "task_clients": task_clients_list,
            "project_statuses": project.statuses, "priority_choices": PRIORITY_CHOICES,
            "errors": {}, "manager_id": user.id,
            "unread_notifications_count": unread_count,
        },
    )


@router.post("/p/{project_uuid}/new/", name="task_create_post")
async def task_create_post(
    request: Request,
    project_uuid: uuid_lib.UUID,
    db: Session = Depends(get_db),
):
    user = require_manager(request, db)
    project = _get_project_by_uuid(db, project_uuid)
    if project.manager_id != user.id:
        raise HTTPException(status_code=403)

    form = await request.form()
    title = form.get("title", "").strip()
    description = form.get("description", "").strip()
    status_id_str = form.get("status_id", "")
    priority = form.get("priority", "medium")
    assignee_id_str = form.get("assignee", "")
    client_ids = [int(x) for x in form.getlist("clients") if x.isdigit()]
    deadline_str = form.get("deadline", "")

    errors = {}
    if not title:
        errors["title"] = "Название обязательно."

    assignee_id = None
    if assignee_id_str and assignee_id_str.isdigit():
        assignee_id = int(assignee_id_str)

    status_id = None
    if status_id_str and status_id_str.isdigit():
        status_id = int(status_id_str)

    deadline = None
    if deadline_str:
        try:
            deadline = date.fromisoformat(deadline_str)
        except ValueError:
            errors["deadline"] = "Неверный формат даты."

    if errors:
        assignees = list(project.executors) + [user]
        task_clients_list = list(project.clients)
        unread_count = get_unread_count(db, user.id)
        return templates.TemplateResponse(
            "projects/task_form.html",
            {
                "request": request, "user": user, "project": project,
                "title": "Новая задача", "task": None,
                "assignees": assignees, "task_clients": task_clients_list,
                "project_statuses": project.statuses, "priority_choices": PRIORITY_CHOICES,
                "errors": errors, "manager_id": user.id,
                "unread_notifications_count": unread_count,
            },
        )

    task = Task(
        title=title, description=description,
        project_id=project.id, status_id=status_id, priority=priority,
        assignee_id=assignee_id, created_by_id=user.id, deadline=deadline,
    )
    db.add(task)
    db.flush()

    if client_ids:
        cls = db.query(User).filter(User.id.in_(client_ids)).all()
        task.clients = cls

    db.commit()

    if assignee_id and assignee_id != user.id:
        _notify(db, [assignee_id], task.id, TYPE_TASK_ASSIGNED, f"Вам назначена задача «{task.title}» в проекте «{project.name}»")
        assignee = db.query(User).filter(User.id == assignee_id).first()
        tg.notify_task_assigned(
            assignee.telegram_id if assignee else None,
            task.title, project.name, str(task.uuid),
            _get_manager_tg(db, project.manager_id, user.id),
        )

    flash(request, f"Задача «{title}» создана.", "success")
    return RedirectResponse(url=f"/p/{project.uuid}/board/", status_code=302)


@router.get("/t/{uuid}/edit/", response_class=HTMLResponse, name="task_edit")
async def task_edit_get(request: Request, uuid: uuid_lib.UUID, db: Session = Depends(get_db)):
    user = require_auth(request, db)
    task = _get_task_by_uuid(db, uuid)
    project = task.project

    if user.is_client():
        raise HTTPException(status_code=403)
    if user.is_executor() and task.assignee_id != user.id:
        raise HTTPException(status_code=403)
    if user.is_manager() and project.manager_id != user.id:
        raise HTTPException(status_code=403)

    assignees = list(project.executors) + [project.manager]
    task_clients_list = list(project.clients)
    unread_count = get_unread_count(db, user.id)
    return templates.TemplateResponse(
        "projects/task_form.html",
        {
            "request": request, "user": user, "task": task, "project": project,
            "title": "Редактировать задачу",
            "assignees": assignees, "task_clients": task_clients_list,
            "project_statuses": project.statuses, "priority_choices": PRIORITY_CHOICES,
            "errors": {}, "manager_id": user.id if user.is_manager() else None,
            "unread_notifications_count": unread_count,
        },
    )


@router.post("/t/{uuid}/edit/", name="task_edit_post")
async def task_edit_post(request: Request, uuid: uuid_lib.UUID, db: Session = Depends(get_db)):
    user = require_auth(request, db)
    task = (
        db.query(Task)
        .filter(Task.uuid == uuid)
        .options(joinedload(Task.status_obj))
        .first()
    )
    if not task:
        raise HTTPException(status_code=404)
    project = task.project

    if user.is_client():
        raise HTTPException(status_code=403)
    if user.is_executor() and task.assignee_id != user.id:
        raise HTTPException(status_code=403)
    if user.is_manager() and project.manager_id != user.id:
        raise HTTPException(status_code=403)

    form = await request.form()
    old_status_name = task.status_obj.name if task.status_obj else ""
    old_status_id = task.status_id
    old_assignee_id = task.assignee_id

    # Load project statuses for validation
    project_statuses = db.query(ProjectStatus).filter(
        ProjectStatus.project_id == project.id
    ).all()
    valid_status_ids = {s.id: s for s in project_statuses}

    if user.is_executor():
        # Только статус
        status_id_str = form.get("status_id", "")
        if status_id_str and status_id_str.isdigit():
            new_status_id = int(status_id_str)
            if new_status_id in valid_status_ids:
                task.status_id = new_status_id
    else:
        # Полное редактирование (менеджер)
        title = form.get("title", "").strip()
        if title:
            if title != task.title:
                db.add(TaskChangeLog(task_id=task.id, changed_by_id=user.id, field_name="Название", old_value=task.title, new_value=title))
            task.title = title

        description = form.get("description", "").strip()
        if description != task.description:
            db.add(TaskChangeLog(task_id=task.id, changed_by_id=user.id, field_name="Описание", old_value=task.description, new_value=description))
        task.description = description

        status_id_str = form.get("status_id", "")
        if status_id_str and status_id_str.isdigit():
            new_status_id = int(status_id_str)
            if new_status_id in valid_status_ids:
                task.status_id = new_status_id

        priority = form.get("priority", task.priority)
        if priority in [p[0] for p in PRIORITY_CHOICES]:
            if priority != task.priority:
                db.add(TaskChangeLog(task_id=task.id, changed_by_id=user.id, field_name="Приоритет", old_value=task.priority, new_value=priority))
            task.priority = priority

        assignee_id_str = form.get("assignee", "")
        new_assignee_id = int(assignee_id_str) if assignee_id_str and assignee_id_str.isdigit() else None
        if new_assignee_id != old_assignee_id:
            old_name = task.assignee.get_display_name() if task.assignee else "—"
            new_user = db.query(User).filter(User.id == new_assignee_id).first() if new_assignee_id else None
            new_name = new_user.get_display_name() if new_user else "—"
            db.add(TaskChangeLog(task_id=task.id, changed_by_id=user.id, field_name="Исполнитель", old_value=old_name, new_value=new_name))
            task.assignee_id = new_assignee_id
            if new_assignee_id and new_assignee_id != user.id:
                _notify(db, [new_assignee_id], task.id, TYPE_TASK_ASSIGNED, f"Вам назначена задача «{task.title}»")
                tg.notify_task_assigned(
                    new_user.telegram_id if new_user else None,
                    task.title, task.project.name, str(task.uuid),
                    _get_manager_tg(db, task.project.manager_id, user.id),
                )

        deadline_str = form.get("deadline", "")
        if deadline_str:
            try:
                new_deadline = date.fromisoformat(deadline_str)
                if new_deadline != task.deadline:
                    db.add(TaskChangeLog(task_id=task.id, changed_by_id=user.id, field_name="Дедлайн", old_value=str(task.deadline or ""), new_value=str(new_deadline)))
                task.deadline = new_deadline
            except ValueError:
                pass
        else:
            if task.deadline:
                db.add(TaskChangeLog(task_id=task.id, changed_by_id=user.id, field_name="Дедлайн", old_value=str(task.deadline), new_value=""))
            task.deadline = None

        client_ids = [int(x) for x in form.getlist("clients") if x.isdigit()]
        task.clients = db.query(User).filter(User.id.in_(client_ids)).all() if client_ids else []

    # Log status change if changed
    if task.status_id != old_status_id:
        new_status_name = valid_status_ids[task.status_id].name if task.status_id in valid_status_ids else ""
        _notify_status_change(db, task, user, old_status_name, new_status_name)

    db.commit()
    flash(request, "Задача обновлена.", "success")
    return RedirectResponse(url=f"/t/{task.uuid}/", status_code=302)


@router.get("/t/{uuid}/delete/", response_class=HTMLResponse, name="task_delete")
async def task_delete_get(request: Request, uuid: uuid_lib.UUID, db: Session = Depends(get_db)):
    user = require_manager(request, db)
    task = _get_task_by_uuid(db, uuid)
    if task.project.manager_id != user.id:
        raise HTTPException(status_code=403)
    unread_count = get_unread_count(db, user.id)
    return templates.TemplateResponse(
        "projects/task_confirm_delete.html",
        {"request": request, "user": user, "task": task, "unread_notifications_count": unread_count},
    )


@router.post("/t/{uuid}/delete/", name="task_delete_post")
async def task_delete_post(request: Request, uuid: uuid_lib.UUID, db: Session = Depends(get_db)):
    user = require_manager(request, db)
    task = _get_task_by_uuid(db, uuid)
    if task.project.manager_id != user.id:
        raise HTTPException(status_code=403)
    project_uuid = task.project.uuid
    db.delete(task)
    db.commit()
    flash(request, "Задача удалена.", "success")
    return RedirectResponse(url=f"/p/{project_uuid}/board/", status_code=302)


@router.post("/t/{uuid}/self-assign/", name="task_self_assign")
async def task_self_assign(request: Request, uuid: uuid_lib.UUID, db: Session = Depends(get_db)):
    user = require_manager(request, db)
    task = _get_task_by_uuid(db, uuid)
    if task.project.manager_id != user.id:
        raise HTTPException(status_code=403)

    old_assignee = task.assignee
    old_name = old_assignee.get_display_name() if old_assignee else "—"
    db.add(TaskChangeLog(
        task_id=task.id, changed_by_id=user.id,
        field_name="Исполнитель", old_value=old_name, new_value=user.get_display_name(),
    ))
    task.assignee_id = user.id
    db.commit()
    flash(request, "Вы назначены исполнителем задачи.", "success")
    return RedirectResponse(url=f"/t/{task.uuid}/", status_code=302)


@router.post("/bulk-update/", name="bulk_task_update")
async def bulk_task_update(request: Request, db: Session = Depends(get_db)):
    user = require_manager(request, db)
    form = await request.form()
    task_uuids = form.getlist("task_uuids[]")
    action = form.get("action")
    value = form.get("value")
    referer = request.headers.get("referer", "/p/")

    if not task_uuids or not action or not value:
        flash(request, "Некорректные данные.", "danger")
        return RedirectResponse(url=referer, status_code=302)

    tasks = (
        db.query(Task)
        .filter(Task.uuid.in_([uuid_lib.UUID(u) for u in task_uuids if len(u) == 36]))
        .join(Project)
        .filter(Project.manager_id == user.id)
        .options(joinedload(Task.assignee), joinedload(Task.project), joinedload(Task.status_obj))
        .all()
    )

    updated = 0
    if action == "change_status":
        if not value.isdigit():
            flash(request, "Неверный статус.", "danger")
            return RedirectResponse(url=referer, status_code=302)
        new_status_id = int(value)
        new_status_obj = db.query(ProjectStatus).filter(ProjectStatus.id == new_status_id).first()
        if not new_status_obj:
            flash(request, "Неверный статус.", "danger")
            return RedirectResponse(url=referer, status_code=302)
        new_status_name = new_status_obj.name
        for task in tasks:
            old_status_id = task.status_id
            if old_status_id != new_status_id:
                old_status_name = task.status_obj.name if task.status_obj else ""
                task.status_id = new_status_id
                db.add(TaskStatusLog(task_id=task.id, changed_by_id=user.id, old_status=old_status_name, new_status=new_status_name))
                db.add(TaskChangeLog(
                    task_id=task.id, changed_by_id=user.id,
                    field_name="Статус",
                    old_value=old_status_name,
                    new_value=new_status_name,
                ))
                updated += 1

    elif action == "change_assignee":
        new_assignee = db.query(User).filter(User.id == int(value), User.role == ROLE_EXECUTOR).first()
        if not new_assignee:
            flash(request, "Исполнитель не найден.", "danger")
            return RedirectResponse(url=referer, status_code=302)
        for task in tasks:
            old_name = task.assignee.get_display_name() if task.assignee else "—"
            task.assignee_id = new_assignee.id
            db.add(TaskChangeLog(
                task_id=task.id, changed_by_id=user.id,
                field_name="Исполнитель", old_value=old_name, new_value=new_assignee.get_display_name(),
            ))
            _notify(db, [new_assignee.id], task.id, TYPE_TASK_ASSIGNED, f"Вам назначена задача «{task.title}»")
            updated += 1

    elif action == "change_priority":
        valid_priorities = [c[0] for c in PRIORITY_CHOICES]
        if value not in valid_priorities:
            flash(request, "Неверный приоритет.", "danger")
            return RedirectResponse(url=referer, status_code=302)
        priority_label = dict(PRIORITY_CHOICES).get(value, value)
        for task in tasks:
            if task.priority != value:
                old_label = dict(PRIORITY_CHOICES).get(task.priority, task.priority)
                task.priority = value
                db.add(TaskChangeLog(
                    task_id=task.id, changed_by_id=user.id,
                    field_name="Приоритет", old_value=old_label, new_value=priority_label,
                ))
                updated += 1

    db.commit()
    if updated:
        flash(request, f"Обновлено задач: {updated}.", "success")
    else:
        flash(request, "Нет изменений.", "info")
    return RedirectResponse(url=referer, status_code=302)


# ── Логи статусов ─────────────────────────────────────────────────────────────

@router.get("/logs/", response_class=HTMLResponse, name="status_logs")
async def status_logs(request: Request, db: Session = Depends(get_db)):
    user = require_manager(request, db)
    logs_q = (
        db.query(TaskStatusLog)
        .join(Task, TaskStatusLog.task_id == Task.id)
        .join(Project, Task.project_id == Project.id)
        .filter(Project.manager_id == user.id)
        .options(
            joinedload(TaskStatusLog.task).joinedload(Task.project),
            joinedload(TaskStatusLog.changed_by),
        )
        .order_by(TaskStatusLog.changed_at.desc())
    )

    project_id = request.query_params.get("project")
    if project_id and project_id.isdigit():
        logs_q = logs_q.filter(Task.project_id == int(project_id))

    executor_id = request.query_params.get("executor")
    if executor_id and executor_id.isdigit():
        logs_q = logs_q.filter(TaskStatusLog.changed_by_id == int(executor_id))

    projects = db.query(Project).filter(Project.manager_id == user.id).all()
    executor_ids_q = (
        db.query(TaskStatusLog.changed_by_id)
        .join(Task, TaskStatusLog.task_id == Task.id)
        .join(Project, Task.project_id == Project.id)
        .filter(Project.manager_id == user.id)
        .distinct()
    )
    executor_id_list = [r[0] for r in executor_ids_q.all() if r[0]]
    executors = db.query(User).filter(User.id.in_(executor_id_list)).all()

    unread_count = get_unread_count(db, user.id)
    return templates.TemplateResponse(
        "projects/status_logs.html",
        {
            "request": request, "user": user,
            "logs": logs_q.limit(200).all(),
            "projects": projects, "executors": executors,
            "selected_project": project_id,
            "selected_executor": executor_id,
            "unread_notifications_count": unread_count,
        },
    )
