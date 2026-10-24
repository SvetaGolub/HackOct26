"""Единое место проверок ролей и границ отделов.

Все сервисы идут через эти функции, поэтому ограничения действуют и в API,
а не только в интерфейсе.
"""
from fastapi import HTTPException
from sqlalchemy import false
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.db.models import Department, User
from app.db.models.enum import UserRole


def is_admin(user: User) -> bool:
    return user.role == UserRole.ADMIN


def is_staff(user: User) -> bool:
    """Бухгалтер или администратор."""
    return user.role in (UserRole.ADMIN, UserRole.ACCOUNTANT)


def can_access_department(actor: User, department_id: int | None) -> bool:
    if is_admin(actor):
        return True
    return actor.department_id is not None and actor.department_id == department_id


def scope_department(stmt: Select, model, actor: User, department_id: int | None = None) -> Select:
    """Ограничивает запрос отделом пользователя. Админ видит всё (и может сузить фильтром)."""
    if is_admin(actor):
        return stmt.where(model.department_id == department_id) if department_id is not None else stmt
    if actor.department_id is None:
        return stmt.where(false())
    if department_id is not None and department_id != actor.department_id:
        return stmt.where(false())
    return stmt.where(model.department_id == actor.department_id)


def not_found(what: str = "Объект не найден") -> HTTPException:
    """404 вместо 403 для чужих отделов: не раскрываем существование объекта."""
    return HTTPException(status_code=404, detail=what)


def forbidden(detail: str = "Недостаточно прав") -> HTTPException:
    """403: используйте как `raise forbidden(...)`."""
    return HTTPException(status_code=403, detail=detail)


def require_roles(actor: User, *roles: UserRole) -> None:
    if actor.role not in roles:
        raise forbidden()


async def resolve_department(db: AsyncSession, actor: User, requested: int | None) -> int:
    """Определяет отдел создаваемого объекта.

    Админ обязан указать отдел явно; остальные работают только в своём.
    """
    if is_admin(actor):
        if requested is None:
            raise HTTPException(status_code=400, detail="Укажите department_id")
        department_id = requested
    else:
        if actor.department_id is None:
            raise HTTPException(status_code=400, detail="Пользователь не привязан к отделу")
        if requested is not None and requested != actor.department_id:
            raise forbidden("Нельзя действовать в чужом отделе")
        department_id = actor.department_id

    if await db.get(Department, department_id) is None:
        raise HTTPException(status_code=404, detail="Отдел не найден")
    return department_id