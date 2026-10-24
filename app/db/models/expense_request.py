from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.models.enum import Currency, ExpenseStatus, Periodicity
from app.db.models.sa_types import str_enum


class ExpenseRequest(Base):
    """Заявка сотрудника на расход. После одобрения порождает RecurringPayment."""

    __tablename__ = "expense_requests"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_request_amount_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[Currency] = mapped_column(str_enum(Currency, 3), nullable=False)
    periodicity: Mapped[Periodicity] = mapped_column(
        str_enum(Periodicity), default=Periodicity.MONTHLY, nullable=False
    )
    desired_date: Mapped[date] = mapped_column(Date, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    status: Mapped[ExpenseStatus] = mapped_column(
        str_enum(ExpenseStatus), default=ExpenseStatus.PENDING, nullable=False, index=True
    )
    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Заполняется при одобрении. Связь в одну сторону, чтобы не было циклических FK.
    recurring_payment_id: Mapped[int | None] = mapped_column(
        ForeignKey("recurring_payments.id", ondelete="SET NULL"), nullable=True
    )
    recurring_payment = relationship("RecurringPayment", lazy="selectin")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ExpenseRequest(id={self.id}, {self.amount} {self.currency}, status={self.status})>"