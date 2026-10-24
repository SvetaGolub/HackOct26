from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.models.enum import Currency
from app.db.models.sa_types import str_enum

if TYPE_CHECKING:
    from app.db.models.recurring_payment import RecurringPayment


class PaymentOccurrence(Base):
    """Конкретный период оплаты: свой срок, своя отметка, своя фактическая дата."""

    __tablename__ = "payment_occurrences"
    __table_args__ = (
        UniqueConstraint("recurring_payment_id", "period", name="uq_occurrence_period"),
        CheckConstraint(
            "(is_paid = 0 AND paid_date IS NULL) OR (is_paid = 1 AND paid_date IS NOT NULL)",
            name="ck_paid_consistency",
        ),
        CheckConstraint("amount > 0", name="ck_occurrence_amount_positive"),
        Index("ix_occurrence_due_paid", "due_date", "is_paid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    recurring_payment_id: Mapped[int] = mapped_column(
        ForeignKey("recurring_payments.id", ondelete="RESTRICT"), nullable=False, index=True
<<<<<<< HEAD
    )
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True, index=True
=======
>>>>>>> 7d3683a (пу пу пу)
    )

    # Снимок названия, суммы и валюты: история не меняется задним числом
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[Currency] = mapped_column(str_enum(Currency, 3), nullable=False)

<<<<<<< HEAD
    # period: первое число месяца; due_date: срок оплаты для этого периода.
=======
    # period: первое число месяца; due_date: срок оплаты этого периода
>>>>>>> 7d3683a (пу пу пу)
    period: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)

    is_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
<<<<<<< HEAD
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # при отмене оплаты NULL
=======
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # при отмене NULL
>>>>>>> 7d3683a (пу пу пу)
    paid_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Когда напоминание ушло в общий Telegram-чат (NULL: ещё не отправляли).
    # Защита от дублей для чата: атомарный UPDATE ... WHERE chat_notified_at IS NULL.
    chat_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    recurring_payment: Mapped["RecurringPayment"] = relationship(
        "RecurringPayment", back_populates="occurrences"
    )

    def is_overdue(self, today: date) -> bool:
        return overdue(self.due_date, self.is_paid, self.paid_date, today)

    def __repr__(self) -> str:
        return f"<PaymentOccurrence(id={self.id}, due={self.due_date}, paid={self.is_paid})>"


def overdue(due: date, is_paid: bool, paid_date: date | None, today: date) -> bool:
    """Просрочка со следующего дня после срока; оплата в день срока вовремя.

    today считайте в часовом поясе из .env, а не через date.today() сервера.
    """
    if is_paid and paid_date is not None:
        return paid_date > due
    return today > due