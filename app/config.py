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
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    @property
    def jwt_secret_key(self) -> str:
        """Возвращает JWT_SECRET_KEY или JWT_SECRET для обратной совместимости."""
        return self.JWT_SECRET_KEY or self.JWT_SECRET

    TELEGRAM_BOT_TOKEN: str = "8675239825:AAHfgAWoudLiE4jxveCa-8io836FLi1WZFg"
    TIMEZONE: str = "Europe/Moscow"

    # Admin
    ADMIN_LOGIN: str = "admin"
    ADMIN_PASSWORD: str = "change-me"

    # CORS
    CORS_ORIGINS: str = "http://localhost:8000"


    @property
    def cors_origins_list(self) -> list[str]:
        """Список разрешенных CORS origin."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


# Глобальный экземпляр настроек
settings = Settings()