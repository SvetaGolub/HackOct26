from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.db.services import AuthService
from app.db.session import get_db
from app.db.models import User, Payment
from app.api.deps import get_current_user
from app.db.schemas import *

router = APIRouter(tags=["Итоги и пользователи"])


@router.get("/payments/summary", response_model=dict)
async def get_payments_summary(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Получение итоговых сумм платежей по валютам (Агрегированные данные из таблицы payment)."""
    # Доступ ко всем суммам логично ограничить Администратором или Бухгалтером
    if current_user.role not in ["administrator", "ACCOUNTANT"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав для просмотра финансовых сводок")

    # Группировка и подсчет суммы
    query = select(Payment.currency, func.sum(Payment.sum).label("total")).group_by(Payment.currency)
    result = await db.execute(query)

    summary = {row.currency: float(row.total) for row in result.all()}
    return {"success": True, "summary": summary}


@router.get("/users", response_model=dict)
async def get_users_list(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Получение списка пользователей (Доступно Администратору)."""
    if current_user.role != "administrator":
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    query = select(User).order_by(User.id.desc())
    result = await db.execute(query)
    users = result.scalars().all()
    return {"success": True, "users": [UserData.model_validate(u) for u in users]}


@router.post("/users", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_user_endpoint(
        user_in: UserCreate,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Создание обычного пользователя или администратора."""
    new_user = await AuthService.register_user(db, user_in, current_user)
    return {"success": True, "user": UserData.model_validate(new_user)}


@router.patch("/users/{id}", response_model=dict)
async def update_user_endpoint(
        id: int,
        update_data: dict,  # Для гибкости или можно завести отдельную Pydantic схему UserUpdate
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Изменение пользователя."""
    if current_user.role != "administrator":
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    query = select(User).where(User.id == id)
    user_res = await db.execute(query)
    user = user_res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    for key, value in update_data.items():
        if hasattr(user, key):
            setattr(user, key, value)

    await db.commit()
    await AuthService.log_access(db, current_user.id, f"Обновлены данные пользователя ID {id}")
    return {"success": True, "user": UserData.model_validate(user)}


@router.delete("/users/{id}", response_model=dict)
async def delete_user_endpoint(
        id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Удаление пользователя из системы."""
    if current_user.role != "administrator":
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    query = select(User).where(User.id == id)
    user_res = await db.execute(query)
    user = user_res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    await db.delete(user)
    await db.commit()
    await AuthService.log_access(db, current_user.id, f"Удален пользователь ID {id}")
    return {"success": True, "message": f"Пользователь {id} успешно удален"}
