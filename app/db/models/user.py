from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.db.models.department import Department
from app.db.models.enum import UserRole
from app.db.models.sa_types import str_enum


class User(Base):
    """Пользователь системы."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[UserRole] = mapped_column(
        str_enum(UserRole, 50), default=UserRole.USER, nullable=False
    )

    # Отдел обязателен для user/accountant (проверяется в сервисе).
    # У админа из .env может быть NULL: он видит все отделы.
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    department: Mapped[Department | None] = relationship(Department, lazy="selectin")

    # Админ из .env: нельзя менять и удалять через панель и API
    is_system: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Telegram ID для личных напоминаний (заполняется при привязке в боте)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"