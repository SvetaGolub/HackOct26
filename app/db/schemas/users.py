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


class TelegramLinkResponse(BaseModel):
    """Одноразовый код для привязки Telegram."""
    code: str = Field(..., description="Код: отправьте боту /start КОД или /link КОД")
    expires_in: int = Field(..., description="Время жизни кода, секунды")
    deep_link: str | None = Field(default=None, description="Ссылка t.me (если задан TELEGRAM_BOT_USERNAME)")