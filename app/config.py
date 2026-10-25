from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "mysql+aiomysql://mysql:mysql@localhost:3306/HackOct"
    DATABASE_PASSWORD: str = "change-me"
    DATABASE_USER: str = "HackOct"

    # JWT
    JWT_SECRET: str = "change-me-in-production"
    JWT_SECRET_KEY: str | None = None  # Алиас для совместимости
    JWT_ALGORITHM: Literal["HS256"] = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, gt=0, le=60)
    API_DOCS_ENABLED: bool = False

    @property
    def jwt_secret_key(self) -> str:
        """Возвращает JWT_SECRET_KEY или JWT_SECRET для обратной совместимости."""
        return self.JWT_SECRET_KEY or self.JWT_SECRET

    # Telegram. Токен обязателен и задаётся только через .env: в коде его хранить нельзя.
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_BOT_USERNAME: str = ""  # для ссылки t.me/<bot>?start=КОД (необязательно)
    # Числовой ID чата или @username канала, куда бот пишет напоминания (ТЗ: «в Telegram-чат»)
    TELEGRAM_CHAT_ID: str = ""
    # Чаты администраторов для обращений; можно также привязать Telegram в панели
    ADMIN_TELEGRAM_CHAT_ID: str = ""
    REMINDER_DAYS: int = 3  # ТЗ: минимум за 3 дня до срока
    TIMEZONE: str = "Europe/Moscow"

    @property
    def telegram_chat_id(self) -> int | str | None:
        """ID чата для общих напоминаний: int для числового ID, строка для @username, None если не задан."""
        value = self.TELEGRAM_CHAT_ID.strip()
        if not value:
            return None
        return int(value) if value.lstrip("-").isdigit() else value

    # Admin
    ADMIN_LOGIN: str = "admin"
    ADMIN_PASSWORD: str = Field(min_length=12)

    # CORS
    CORS_ORIGINS: str = "http://localhost:8000"

    @property
    def cors_origins_list(self) -> list[str]:
        """Список разрешенных CORS origin."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_security_settings(self):
        if "change-me" in self.DATABASE_URL.lower():
            raise ValueError("Set a unique DATABASE_URL password")
        if len(self.jwt_secret_key.encode("utf-8")) < 32:
            raise ValueError("JWT_SECRET_KEY must contain at least 32 bytes")
        if self.jwt_secret_key == "change-me-in-production":
            raise ValueError("Set a unique JWT_SECRET_KEY")
        if self.ADMIN_PASSWORD.strip().lower() in {"change-me", "password", "admin"}:
            raise ValueError("Set a unique ADMIN_PASSWORD")
        if "*" in self.cors_origins_list:
            raise ValueError("CORS_ORIGINS must list trusted origins, not '*'")
        return self


# Глобальный экземпляр настроек
settings = Settings()