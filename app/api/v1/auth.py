from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.schemas import *
from app.db.services import *
from app.api.deps import get_current_user
from app.db.models import User

router = APIRouter(prefix="/auth", tags=["Авторизация"])

@router.post("/login", response_model=AuthResponse)
async def login(login_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Вход по логину (email) и паролю."""
    return await AuthService.authenticate_user(db, login_data)

@router.get("/me", response_model=UserData)
async def get_me(current_user: User = Depends(get_current_user)):
    """Получение данных текущего пользователя сессии."""
    return current_user

@router.post("/logout", response_model=LogoutResponse)
async def logout(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Завершение текущей сессии."""
    await AuthService.log_access(db, current_user.id, "Пользователь вышел из системы")
    return LogoutResponse()
