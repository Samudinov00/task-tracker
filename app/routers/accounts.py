"""
Роуты управления пользователями (аналог accounts/views.py).
"""
from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional

from app.database import SessionLocal
from app.dependencies import get_db, require_auth, require_manager
from app.models.user import User, ROLE_LABELS, ROLE_EXECUTOR

ROLE_CHOICES = list(ROLE_LABELS.items())
from app.utils import flash, templates

router = APIRouter()


# ── Профиль ──────────────────────────────────────────────────────────────────

@router.get("/accounts/profile/", response_class=HTMLResponse, name="profile")
async def profile_get(request: Request, db: Session = Depends(get_db)):
    user = require_auth(request, db)
    return templates.TemplateResponse(
        "accounts/profile.html",
        {"request": request, "user": user, "errors": {}, "password_errors": {}},
    )


@router.post("/accounts/profile/", name="profile_post")
async def profile_post(
    request: Request,
    db: Session = Depends(get_db),
    save_profile: Optional[str] = Form(None),
    save_password: Optional[str] = Form(None),
    first_name: str = Form(""),
    last_name: str = Form(""),
    old_password: str = Form(""),
    new_password1: str = Form(""),
    new_password2: str = Form(""),
):
    user = require_auth(request, db)

    if save_profile is not None:
        form = await request.form()
        tg_username = form.get("telegram_username", "").strip().lstrip("@") or None
        user.first_name = first_name
        user.last_name = last_name
        user.telegram_username = tg_username
        db.commit()
        flash(request, "Профиль успешно обновлён.", "success")
        return RedirectResponse(url="/accounts/profile/", status_code=302)

    if save_password is not None:
        errors = {}
        if not user.verify_password(old_password):
            errors["old_password"] = "Неверный текущий пароль."
        elif not new_password1:
            errors["new_password1"] = "Введите новый пароль."
        elif new_password1 != new_password2:
            errors["new_password2"] = "Пароли не совпадают."
        elif len(new_password1) < 8:
            errors["new_password1"] = "Пароль слишком короткий (минимум 8 символов)."

        if errors:
            return templates.TemplateResponse(
                "accounts/profile.html",
                {"request": request, "user": user, "errors": {}, "password_errors": errors},
            )
        user.set_password(new_password1)
        db.commit()
        flash(request, "Пароль успешно изменён.", "success")
        return RedirectResponse(url="/accounts/profile/", status_code=302)

    return RedirectResponse(url="/accounts/profile/", status_code=302)


# ── Список пользователей (менеджер) ──────────────────────────────────────────

@router.get("/accounts/users/", response_class=HTMLResponse, name="user_list")
async def user_list(request: Request, db: Session = Depends(get_db)):
    user = require_manager(request, db)
    users = (
        db.query(User)
        .filter(User.id != user.id)
        .order_by(User.role, User.username)
        .all()
    )
    return templates.TemplateResponse(
        "accounts/user_list.html",
        {"request": request, "user": user, "users": users},
    )


# ── Создание пользователя ────────────────────────────────────────────────────

@router.get("/accounts/users/create/", response_class=HTMLResponse, name="user_create")
async def user_create_get(request: Request, db: Session = Depends(get_db)):
    user = require_manager(request, db)
    return templates.TemplateResponse(
        "accounts/user_form.html",
        {
            "request": request,
            "user": user,
            "title": "Создать пользователя",
            "edit_user": None,
            "role_choices": ROLE_CHOICES,
            "errors": {},
        },
    )


@router.post("/accounts/users/create/", name="user_create_post")
async def user_create_post(
    request: Request,
    db: Session = Depends(get_db),
    username: str = Form(...),
    first_name: str = Form(""),
    last_name: str = Form(""),
    role: str = Form(ROLE_EXECUTOR),
    password1: str = Form(...),
    password2: str = Form(...),
):
    manager = require_manager(request, db)
    errors = {}

    if db.query(User).filter(User.username == username).first():
        errors["username"] = "Пользователь с таким логином уже существует."
    if not password1:
        errors["password1"] = "Введите пароль."
    elif password1 != password2:
        errors["password2"] = "Пароли не совпадают."
    elif len(password1) < 8:
        errors["password1"] = "Пароль слишком короткий (минимум 8 символов)."

    if errors:
        return templates.TemplateResponse(
            "accounts/user_form.html",
            {
                "request": request,
                "user": manager,
                "title": "Создать пользователя",
                "edit_user": None,
                "role_choices": ROLE_CHOICES,
                "errors": errors,
                "form_data": {"username": username, "first_name": first_name, "last_name": last_name, "role": role},
            },
        )

    form = await request.form()
    tg_username = form.get("telegram_username", "").strip().lstrip("@") or None

    new_user = User(username=username, first_name=first_name, last_name=last_name,
                    role=role, telegram_username=tg_username)
    new_user.set_password(password1)
    db.add(new_user)
    db.commit()
    flash(request, f"Пользователь «{username}» создан.", "success")
    return RedirectResponse(url="/accounts/users/", status_code=302)


# ── Редактирование пользователя ──────────────────────────────────────────────

@router.get("/accounts/users/{pk}/edit/", response_class=HTMLResponse, name="user_edit")
async def user_edit_get(request: Request, pk: int, db: Session = Depends(get_db)):
    manager = require_manager(request, db)
    edit_user = db.query(User).filter(User.id == pk).first()
    if not edit_user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "accounts/user_form.html",
        {
            "request": request,
            "user": manager,
            "title": "Редактировать пользователя",
            "edit_user": edit_user,
            "role_choices": ROLE_CHOICES,
            "errors": {},
        },
    )


@router.post("/accounts/users/{pk}/edit/", name="user_edit_post")
async def user_edit_post(
    request: Request,
    pk: int,
    db: Session = Depends(get_db),
    username: str = Form(...),
    first_name: str = Form(""),
    last_name: str = Form(""),
    role: str = Form(ROLE_EXECUTOR),
    is_active: bool = Form(False),
):
    manager = require_manager(request, db)
    edit_user = db.query(User).filter(User.id == pk).first()
    if not edit_user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404)

    errors = {}
    existing = db.query(User).filter(User.username == username, User.id != pk).first()
    if existing:
        errors["username"] = "Пользователь с таким логином уже существует."

    if errors:
        return templates.TemplateResponse(
            "accounts/user_form.html",
            {
                "request": request,
                "user": manager,
                "title": "Редактировать пользователя",
                "edit_user": edit_user,
                "role_choices": ROLE_CHOICES,
                "errors": errors,
            },
        )

    form = await request.form()
    tg_username = form.get("telegram_username", "").strip().lstrip("@") or None
    edit_user.username = username
    edit_user.first_name = first_name
    edit_user.last_name = last_name
    edit_user.role = role
    edit_user.is_active = is_active
    edit_user.telegram_username = tg_username
    db.commit()
    flash(request, "Данные пользователя обновлены.", "success")
    return RedirectResponse(url="/accounts/users/", status_code=302)


# ── Сброс пароля (менеджером) ────────────────────────────────────────────────

@router.get("/accounts/users/{pk}/set-password/", response_class=HTMLResponse, name="user_set_password")
async def user_set_password_get(request: Request, pk: int, db: Session = Depends(get_db)):
    manager = require_manager(request, db)
    target = db.query(User).filter(User.id == pk).first()
    if not target:
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "accounts/user_set_password.html",
        {"request": request, "user": manager, "target": target, "errors": {}},
    )


@router.post("/accounts/users/{pk}/set-password/", name="user_set_password_post")
async def user_set_password_post(
    request: Request,
    pk: int,
    db: Session = Depends(get_db),
    new_password1: str = Form(...),
    new_password2: str = Form(...),
):
    manager = require_manager(request, db)
    target = db.query(User).filter(User.id == pk).first()
    if not target:
        from fastapi import HTTPException
        raise HTTPException(status_code=404)

    errors = {}
    if not new_password1:
        errors["new_password1"] = "Введите пароль."
    elif new_password1 != new_password2:
        errors["new_password2"] = "Пароли не совпадают."

    if errors:
        return templates.TemplateResponse(
            "accounts/user_set_password.html",
            {"request": request, "user": manager, "target": target, "errors": errors},
        )

    target.set_password(new_password1)
    db.commit()
    flash(request, f"Пароль пользователя «{target.username}» сброшен.", "success")
    return RedirectResponse(url="/accounts/users/", status_code=302)


# ── Удаление пользователя ────────────────────────────────────────────────────

@router.get("/accounts/users/{pk}/delete/", response_class=HTMLResponse, name="user_delete")
async def user_delete_get(request: Request, pk: int, db: Session = Depends(get_db)):
    manager = require_manager(request, db)
    target = db.query(User).filter(User.id == pk).first()
    if not target:
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "accounts/user_confirm_delete.html",
        {"request": request, "user": manager, "target": target},
    )


@router.post("/accounts/users/{pk}/delete/", name="user_delete_post")
async def user_delete_post(request: Request, pk: int, db: Session = Depends(get_db)):
    manager = require_manager(request, db)
    target = db.query(User).filter(User.id == pk).first()
    if not target:
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    db.delete(target)
    db.commit()
    flash(request, "Пользователь удалён.", "success")
    return RedirectResponse(url="/accounts/users/", status_code=302)
