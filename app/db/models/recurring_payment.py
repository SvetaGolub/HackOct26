from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.models.enum import Currency, Periodicity
from app.db.models.sa_types import str_enum

if TYPE_CHECKING:
    from app.db.models.payment_occurrence import PaymentOccurrence


class RecurringPayment(Base):
    """Регулярный платёж (шаблон): аренда, сервер, подписка."""

    __tablename__ = "recurring_payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_recurring_amount_positive"),
        CheckConstraint("anchor_day BETWEEN 1 AND 31", name="ck_recurring_anchor_day"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[Currency] = mapped_column(str_enum(Currency, 3), nullable=False)
    periodicity: Mapped[Periodicity] = mapped_column(
        str_enum(Periodicity), default=Periodicity.MONTHLY, nullable=False
    )

    # Ближайшая дата оплаты и "якорный" день месяца.
    # Якорь нужен, чтобы после 28 февраля вернуться на 31 марта, а не застрять на 28.
    first_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    anchor_day: Mapped[int] = mapped_column(Integer, nullable=False)

    # Отдел, которому принадлежит платёж (граница видимости)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    # Мягкое удаление: история сохраняется, напоминания прекращаются
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    occurrences: Mapped[list["PaymentOccurrence"]] = relationship(
        "PaymentOccurrence",
        back_populates="recurring_payment",
        order_by="PaymentOccurrence.period",
    )

    def __repr__(self) -> str:
        return f"<RecurringPayment(id={self.id}, title={self.title}, {self.amount} {self.currency})>"