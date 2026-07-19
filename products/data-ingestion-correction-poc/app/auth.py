import hashlib
import hmac
import os

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import AdminUser, EndUser

PBKDF2_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt_hex, digest_hex = password_hash.split("$", 1)
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(digest_hex)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return hmac.compare_digest(actual, expected)


def verify_admin_password(password: str) -> bool:
    return hmac.compare_digest(password, settings.ADMIN_PASSWORD)


def verify_enduser_credentials(db: Session, username: str, password: str) -> EndUser | None:
    user = db.query(EndUser).filter(EndUser.username == username).first()
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def verify_admin_user_credentials(db: Session, username: str, password: str) -> AdminUser | None:
    user = db.query(AdminUser).filter(AdminUser.username == username).first()
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


# Three roles: "master_admin" (the single shared ADMIN_PASSWORD login, no DB row) and "admin"
# (a named AdminUser account, created by the master admin) both get full admin access — the
# only difference is that only "master_admin" can manage admin accounts. "enduser" is separate.
ADMIN_ROLES = {"master_admin", "admin"}


def _require_roles(request: Request, roles: set[str], *, as_page: bool):
    if request.session.get("role") not in roles:
        if as_page:
            raise HTTPException(status_code=303, headers={"Location": "/login"})
        raise HTTPException(status_code=403, detail="Not authorized")


def require_admin_page(request: Request):
    _require_roles(request, ADMIN_ROLES, as_page=True)


def require_admin(request: Request):
    _require_roles(request, ADMIN_ROLES, as_page=False)


def require_master_admin_page(request: Request):
    _require_roles(request, {"master_admin"}, as_page=True)


def require_master_admin(request: Request):
    _require_roles(request, {"master_admin"}, as_page=False)


def require_enduser_page(request: Request):
    _require_roles(request, {"enduser"}, as_page=True)


def require_enduser(request: Request):
    _require_roles(request, {"enduser"}, as_page=False)


def current_enduser_id(request: Request) -> int:
    enduser_id = request.session.get("enduser_id")
    if enduser_id is None:
        raise HTTPException(status_code=403, detail="Not authorized")
    return enduser_id
