from pydantic import BaseModel, Field

from app.db.models.enum import UserRole


class UserLogin(BaseModel):
    """Вход по логину и паролю (для всех ролей)."""
    login: str = Field(..., min_length=1, max_length=255, description="Логин")
    # Нижней границы длины нет намеренно: пароль админа из .env может быть коротким
    password: str = Field(..., min_length=1, max_length=128, description="Пароль")


class UserCreate(BaseModel):
    """Создание обычного пользователя администратором (роль всегда user)."""
    login: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    telegram_id: int | None = Field(default=None, description="Telegram ID для напоминаний")


class UserUpdate(BaseModel):
    """PATCH /users/{id}: передаются только изменяемые поля."""
    model_config = {"extra": "forbid"}

    login: str | None = Field(default=None, min_length=3, max_length=255)
    password: str | None = Field(default=None, min_length=6, max_length=128)
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    telegram_id: int | None = None


class UserData(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    login: str
    full_name: str
    role: UserRole
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


class TelegramLinkComplete(BaseModel):
    """Код, полученный от бота для привязки Telegram к текущему аккаунту."""
    code: str = Field(..., min_length=10, max_length=10, pattern=r"^[A-Z0-9]{10}$")