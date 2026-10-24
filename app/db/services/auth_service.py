from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import HTTPException
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import User
from app.db.models.enum import UserRole
from app.db.schemas import AuthResponse, UserData, UserLogin

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        minutes = getattr(settings, "JWT_EXPIRE_MINUTES", 60)
        expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=minutes))
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.JWT_ALGORITHM)

    @classmethod
    async def authenticate_user(cls, db: AsyncSession, login_data: UserLogin) -> AuthResponse:
        user = (await db.execute(select(User).where(User.email == login_data.email))).scalar_one_or_none()
        if not user or not cls.verify_password(login_data.password, user.password_hash):
            raise HTTPException(
                status_code=401, detail="Неверный email или пароль", headers={"WWW-Authenticate": "Bearer"}
            )
        # Роль в токен не кладём: актуальную роль всегда берём из БД
        token = cls.create_access_token({"sub": str(user.id)})
        return AuthResponse(success=True, user=UserData.model_validate(user), accessToken=token)

    @classmethod
    async def get_current_user(cls, db: AsyncSession, token: str) -> User:
        """Пользователь по токену. Используйте в зависимости FastAPI на каждом защищённом эндпоинте."""
        credentials_error = HTTPException(
            status_code=401, detail="Требуется авторизация", headers={"WWW-Authenticate": "Bearer"}
        )
        try:
            payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.JWT_ALGORITHM])
            user_id = int(payload["sub"])
        except (jwt.PyJWTError, KeyError, ValueError):
            raise credentials_error
        user = await db.get(User, user_id)
        if user is None:  # пользователя удалили: токен больше не действует
            raise credentials_error
        return user

    @classmethod
    async def ensure_system_admin(cls, db: AsyncSession) -> None:
        """Создаёт/синхронизирует администратора из .env. Вызывать при старте приложения.

        Нужны ADMIN_EMAIL и ADMIN_PASSWORD в настройках. Повторный запуск ничего не дублирует.
        """
        email, password = settings.ADMIN_EMAIL, settings.ADMIN_PASSWORD
        admin = (await db.execute(select(User).where(User.is_system.is_(True)))).scalar_one_or_none()

        if admin is None:
            clash = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if clash is not None:
                raise RuntimeError(f"Пользователь {email} уже существует и не является системным администратором")
            db.add(User(
                email=email, password_hash=cls.get_password_hash(password),
                full_name="Administrator", role=UserRole.ADMIN, department_id=None, is_system=True,
            ))
        else:
            admin.email = email
            if not cls.verify_password(password, admin.password_hash):
                admin.password_hash = cls.get_password_hash(password)
        await db.commit()