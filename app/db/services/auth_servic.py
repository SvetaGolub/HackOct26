import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status

from app.db.models import User, AccessLog
from app.db.schemas import *
from app.config import settings  # Предполагается наличие настроек с SECRET_KEY

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Проверка совпадения пароля."""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Хэширование пароля перед сохранением в БД."""
        return pwd_context.hash(password)

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Генерация JWT токена сессии."""
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=60))
        to_encode.update({"exp": expire})
        # SECRET_KEY и ALGORITHM берутся из конфигурации приложения
        encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.JWT_ALGORITHM)
        return encoded_jwt

    @classmethod
    async def log_access(cls, db: AsyncSession, user_id: Optional[int], result: str):
        """Запись операции в логи безопасности (AccessLog)."""
        log_entry = AccessLog(user_id=user_id, result=result)
        db.add(log_entry)
        await db.commit()

    @classmethod
    async def register_user(cls, db: AsyncSession, user_in: UserCreate, current_admin: User) -> User:
        """Регистрация нового пользователя (только для Администратора)."""
        # Проверка по презентации: только админ создает пользователей
        if current_admin.role != "administrator":
            await cls.log_access(db, current_admin.id, f"Ошибка прав: попытка создать пользователя {user_in.email}")
            raise HTTPException(status_code=403, detail="Недостаточно прав для создания пользователя")

        # Проверка существования email
        query = select(User).where(User.email == user_in.email)
        result = await db.execute(query)
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")

        hashed_password = cls.get_password_hash(user_in.password)

        new_user = User(
            email=user_in.email,
            password_hash=hashed_password,
            full_name=user_in.full_name,
            role=user_in.role.value,
            department=user_in.department,
            telegram_id=user_in.telegram_id
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        await cls.log_access(db, current_admin.id, f"Создан пользователь {new_user.email} с рольвем {new_user.role}")
        return new_user

    @classmethod
    async def authenticate_user(cls, db: AsyncSession, login_data: UserLogin) -> AuthResponse:
        """Аутентификация пользователя (Вход)."""
        query = select(User).where(User.email == login_data.email)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user or not cls.verify_password(login_data.password, user.password_hash):
            # Если логин не удался, user_id = None
            await cls.log_access(db, None, f"Неудачная попытка входа для email: {login_data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный email или пароль",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Успешный вход
        await cls.log_access(db, user.id, f"Успешный вход в систему")

        token = cls.create_access_token(data={"sub": str(user.id), "role": user.role})

        user_data = UserData.model_validate(user)
        return AuthResponse(success=True, user=user_data, accessToken=token)
