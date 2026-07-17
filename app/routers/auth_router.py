from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import verify_admin_password, verify_admin_user_credentials, verify_enduser_credentials
from app.db import get_db

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login")
def login_page(request: Request, error: str | None = None):
    return templates.TemplateResponse(
        request, "login.html", {"error": error}
    )


@router.post("/login")
def login_submit(
    request: Request,
    role: str = Form(...),
    password: str = Form(...),
    username: str = Form(default=""),
    db: Session = Depends(get_db),
):
    if role == "master_admin":
        if verify_admin_password(password):
            request.session.clear()
            request.session["role"] = "master_admin"
            return RedirectResponse(url="/admin", status_code=303)
    elif role == "admin":
        admin_user = verify_admin_user_credentials(db, username, password)
        if admin_user is not None:
            request.session.clear()
            request.session["role"] = "admin"
            request.session["admin_username"] = admin_user.username
            return RedirectResponse(url="/admin", status_code=303)
    elif role == "enduser":
        user = verify_enduser_credentials(db, username, password)
        if user is not None:
            request.session.clear()
            request.session["role"] = "enduser"
            request.session["enduser_id"] = user.id
            request.session["enduser_username"] = user.username
            return RedirectResponse(url="/review", status_code=303)

    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": "Invalid credentials"},
        status_code=401,
    )


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
