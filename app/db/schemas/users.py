from app.db.models.enum import *
from pydantic import BaseModel, Field, EmailStr

class UserLogin(BaseModel):
    """Универсальная схема для входа в систему (для всех ролей)."""
    email: EmailStr = Field(..., description="Электронная почта (логин)")
    password: str = Field(..., min_length=6, max_length=128, description="Пароль")

class UserCreate(BaseModel):
    """Схема для создания (регистрации) нового пользователя администратором."""
    email: EmailStr = Field(..., description="Электронная почта")
    password: str = Field(..., min_length=6, max_length=128, description="Пароль")
    full_name: str = Field(..., max_length=255, description="ФИО сотрудника")
    role: UserRole = Field(default=UserRole.USER, description="Роль в системе")
    department: str = Field(..., max_length=255, description="Отдел / Департамент")
    telegram_id: int = Field(..., description="Telegram ID чата для отправки уведомлений")

class UserData(BaseModel):
    """Данные пользователя, возвращаемые в ответах API."""
    model_config = {"from_attributes": True}

    id: int = Field(..., description="ID пользователя в БД")
    email: EmailStr = Field(..., description="Электронная почта")
    full_name: str = Field(..., description="ФИО сотрудника")
    role: UserRole = Field(..., description="Роль в системе")
    department: str = Field(..., description="Отдел / Департамент")
    telegram_id: int = Field(..., description="Telegram ID для уведомлений")

class AuthResponse(BaseModel):
    """Единая схема успешного ответа аутентификации."""
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

