from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.db.models.enum import UserRole
from app.db.schemas.department import DepartmentData

# Через API создаются только эти роли. Администратор задаётся через .env.
AssignableRole = Literal["user", "accountant"]


class UserLogin(BaseModel):
    """Вход в систему (для всех ролей)."""
    email: EmailStr = Field(..., description="Электронная почта")
    # Нижней границы длины нет намеренно: пароль админа из .env может быть коротким
    password: str = Field(..., min_length=1, max_length=128, description="Пароль")


class UserCreate(BaseModel):
    """Создание пользователя или бухгалтера администратором."""
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)
    role: AssignableRole = "user"
    department_id: int = Field(..., description="ID отдела")
    telegram_id: int | None = Field(default=None, description="Telegram ID для напоминаний")


class UserUpdate(BaseModel):
    """PATCH /users/{id}: передаются только изменяемые поля."""
    model_config = {"extra": "forbid"}

    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=6, max_length=128)
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: AssignableRole | None = None
    department_id: int | None = None
    telegram_id: int | None = None


class UserData(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    department_id: int | None = None
    department: DepartmentData | None = None
    is_system: bool = False
    telegram_id: int | None = None


class AuthResponse(BaseModel):
    """Успешный ответ аутентификации."""
    success: bool = Field(default=True, description="Флаг успешности запроса")
    user: UserData = Field(..., description="Данные авторизованного пользователя")
    accessToken: str = Field(..., description="JWT токен сессии")


class LogoutResponse(BaseModel):
    """Ответ при выходе из системы."""
    success: bool = Field(default=True, description="Флаг успешности запроса")
    message: str = Field(
        default="Выход выполнен успешно. Удалите токен на стороне клиента.",
        description="Инструкция для фронтенда",
    )