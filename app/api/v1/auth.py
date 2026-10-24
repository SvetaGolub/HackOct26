from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.schemas import AuthResponse, LogoutResponse, UserData, UserLogin
from app.db.services import AuthService
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["Авторизация"])


@router.post("/login", response_model=AuthResponse)
async def login(login_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Вход по email и паролю."""
    return await AuthService.authenticate_user(db, login_data)


@router.get("/me", response_model=UserData)
async def get_me(current_user: User = Depends(get_current_user)):
    """Данные текущего пользователя."""
    return current_user


@router.post("/logout", response_model=LogoutResponse)
async def logout(current_user: User = Depends(get_current_user)):
    """Завершение сессии. Токен stateless: клиент удаляет его у себя."""
    return LogoutResponse()