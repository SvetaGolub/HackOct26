from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.deps import require_admin
from app.db.models import User
from app.db.models.enum import UserRole
from app.db.schemas import UserCreate, UserData, UserUpdate
from app.db.services.auth_service import AuthService
from app.db.session import get_db

router = APIRouter(tags=["Пользователи"])


async def _get_regular_user(db: AsyncSession, user_id: int) -> User:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if user.role == UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="Учётную запись администратора нельзя изменить через API")
    return user


@router.get("/users", response_model=list[UserData])
async def list_users(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(User).order_by(User.id))).scalars().all()


@router.post("/users", response_model=UserData, status_code=201)
async def create_user(user_in: UserCreate, admin: User = Depends(require_admin),
                      db: AsyncSession = Depends(get_db)):
    return await AuthService.register_user(db, user_in, admin)


@router.patch("/users/{user_id}", response_model=UserData)
async def update_user(user_id: int, data: UserUpdate, admin: User = Depends(require_admin),
                      db: AsyncSession = Depends(get_db)):
    user = await _get_regular_user(db, user_id)
    changes = data.model_dump(exclude_unset=True)

    if "login" in changes and changes["login"] != user.login:
        taken = (await db.execute(select(User).where(User.login == changes["login"]))).scalar_one_or_none()
        if taken:
            raise HTTPException(status_code=400, detail="Логин уже занят")
    if "password" in changes:
        user.password_hash = AuthService.get_password_hash(changes.pop("password"))
    for key, value in changes.items():
        setattr(user, key, value)

    await db.commit()
    await db.refresh(user)
    await AuthService.log_access(db, admin.id, f"Обновлён пользователь ID {user_id}")
    return user


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: int, admin: User = Depends(require_admin),
                      db: AsyncSession = Depends(get_db)):
    user = await _get_regular_user(db, user_id)
    await db.delete(user)
    await db.commit()
    await AuthService.log_access(db, admin.id, f"Удалён пользователь ID {user_id}")
    return Response(status_code=204)