from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, security
from app.db.models import User
from app.config import settings
from app.db.schemas import (
    AuthResponse, LogoutResponse, MessageResponse, TelegramLinkResponse, UserData, UserLogin,
)
from app.db.services import AuthService, TelegramLinkService
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["Авторизация"])


@router.post("/login", response_model=AuthResponse)
async def login(login_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Вход по логину (email) и паролю."""
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


@router.post("/telegram-link", response_model=TelegramLinkResponse)
async def create_telegram_link(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Одноразовый код (10 минут) для привязки Telegram: отправьте боту /link КОД."""
    code, ttl = await TelegramLinkService.create_code(db, current_user)
    username = getattr(settings, "TELEGRAM_BOT_USERNAME", "")
    deep_link = f"https://t.me/{username}?start={code}" if username else None
    return TelegramLinkResponse(code=code, expires_in=ttl, deep_link=deep_link)


@router.delete("/telegram-link", response_model=MessageResponse)
async def unlink_telegram(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Отвязать Telegram от аккаунта."""
    done = await TelegramLinkService.unlink_user(db, current_user)
    return MessageResponse(message="Telegram отвязан" if done else "Telegram не был привязан")