from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.db.models.enum import UserRole
from app.db.models.sa_types import str_enum


class User(Base):
    """Пользователь системы: админ (из .env) или обычный пользователь."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # ТЗ: вход по логину и паролю
    login: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[UserRole] = mapped_column(
        str_enum(UserRole, 50), default=UserRole.USER, nullable=False
    )

    # Админ из .env: нельзя менять и удалять через панель и API
    is_system: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Telegram ID для личных напоминаний (заполняется при привязке в боте)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, login={self.login}, role={self.role})>"