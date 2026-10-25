from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, security
from app.db.models import User
from app.db.schemas import (
    AuthResponse, LogoutResponse, MessageResponse, TelegramLinkComplete, UserData, UserLogin,
)
from app.db.services import AuthService, TelegramLinkService
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["Авторизация"])


@router.post("/login", response_model=AuthResponse)
async def login(login_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Вход по логину и паролю."""
    return await AuthService.authenticate_user(db, login_data)


@router.get("/me", response_model=UserData)
async def get_me(current_user: User = Depends(get_current_user)):
    """Данные текущего пользователя."""
    return current_user


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отзывает текущую серверную сессию."""
    await AuthService.logout(db, credentials.credentials)
    return LogoutResponse()


@router.post("/telegram-link", response_model=MessageResponse)
async def complete_telegram_link(
    payload: TelegramLinkComplete,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Привязать Telegram по одноразовому коду, полученному командой /link в боте."""
    user = await TelegramLinkService.consume(db, payload.code, current_user)
    if user is None:
        raise HTTPException(status_code=400, detail="Код неверный или истёк. Получите новый в Telegram-боте.")
    return MessageResponse(message="Telegram успешно привязан")


@router.delete("/telegram-link", response_model=MessageResponse)
async def unlink_telegram(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Отвязать Telegram от аккаунта."""
    done = await TelegramLinkService.unlink_user(db, current_user)
    return MessageResponse(message="Telegram отвязан" if done else "Telegram не был привязан")