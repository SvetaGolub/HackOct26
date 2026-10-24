from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.schemas import UserCreate, UserData, UserUpdate
from app.db.services import UserService
from app.db.session import get_db

router = APIRouter(tags=["Пользователи"])
# Все права проверяются в UserService (только администратор), а не здесь:
# так ограничения действуют для любого клиента API.


@router.get("/users", response_model=list[UserData])
async def list_users(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await UserService.list_users(db, user, limit, offset)


@router.post("/users", response_model=UserData, status_code=201)
async def create_user(
    payload: UserCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await UserService.create_user(db, payload, user)


@router.patch("/users/{user_id}", response_model=UserData)
async def update_user(
    user_id: int, payload: UserUpdate,
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    return await UserService.update_user(db, user_id, payload, user)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    await UserService.delete_user(db, user_id, user)
    return Response(status_code=204)