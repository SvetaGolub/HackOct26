"""Единое место проверок ролей.

Все сервисы идут через эти функции, поэтому ограничения действуют и в API,
а не только в интерфейсе. Ролей две: администратор и пользователь.
"""
from fastapi import HTTPException

from app.db.models import User
from app.db.models.enum import UserRole


def is_admin(user: User) -> bool:
    return user.role == UserRole.ADMIN


def not_found(what: str = "Объект не найден") -> HTTPException:
    return HTTPException(status_code=404, detail=what)


def forbidden(detail: str = "Недостаточно прав") -> HTTPException:
    """403: используйте как `raise forbidden(...)`."""
    return HTTPException(status_code=403, detail=detail)


def require_roles(actor: User, *roles: UserRole) -> None:
    if actor.role not in roles:
        raise forbidden()