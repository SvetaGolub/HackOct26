from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.db.models import Payment
from app.db.models.enum import UserRole


class User(Base):
    """Модель пользователя."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Роль для разграничения прав (Администратор / Бухгалтер / Пользователь)
    role: Mapped[UserRole] = mapped_column(String(50), default=UserRole.USER, nullable=False)
    department: Mapped[str] = mapped_column(String(255), nullable=False)

    # Telegram ID для отправки уведомлений
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # Связь с платежами
    id_payments: Mapped[list["Payment"] | None ] = relationship("Payment", back_populates="user")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, login={self.email}, role={self.role})>"