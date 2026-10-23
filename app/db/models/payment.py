from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, String, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.models import User
from app.db.models.enum import CURRENCY


class Payment(Base):
    """Модель платежа."""

    __tablename__ = "payment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Кто создал / отвечает за платеж
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    description: Mapped[str] = mapped_column(String(255), index=True, nullable=False)  # Аренда, подписка и т.д.
    status: Mapped[str] = mapped_column(String(255), index=True, nullable=False)  # Оплачен, Просрочен, Ожидает

    sum: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[CURRENCY] = mapped_column(String(10), default="RUB", nullable=False)

    # Время создания записи
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Срок оплаты (Дедлайн) — критично для уведомлений за 3 дня
    due_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),  # Хранит дату и время с учетом часового пояса
        server_default=func.now(),# Значение по умолчанию будет генерироваться на стороне самой базы данных. Защищает от рассинхрона времени
        nullable=False,
    )

    # Дата фактической оплаты (может быть пустой, пока не оплачено)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Обратная связь с пользователем
    user: Mapped["User"] = relationship("User", back_populates="payments")

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, type={self.type}, sum={self.sum}, status={self.status})>"