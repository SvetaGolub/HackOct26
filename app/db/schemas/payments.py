from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from app.db.models.enum import Currency, Periodicity
from app.db.models.payment_occurrence import overdue


class OccurrenceStatusFilter(str, Enum):
    """Фильтр списка периодов."""
    PAID = "paid"
    UNPAID = "unpaid"
    OVERDUE = "overdue"


class RecurringPaymentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    amount: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)
    currency: Currency
    first_due_date: date = Field(..., description="Дата ближайшей оплаты")
    periodicity: Periodicity = Periodicity.MONTHLY
    department_id: int | None = Field(
        default=None, description="Обязателен для администратора; бухгалтер создаёт только в своём отделе"
    )


class RecurringPaymentData(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    title: str
    amount: Decimal
    currency: Currency
    periodicity: Periodicity
    first_due_date: date
    department_id: int
    is_active: bool
    deleted_at: datetime | None = None
    created_at: datetime


class OccurrenceData(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    recurring_payment_id: int
    department_id: int
    title: str
    amount: Decimal
    currency: Currency
    period: date
    original_due_date: date
    due_date: date
    reschedule_reason: str | None = None
    is_paid: bool
    status: str = Field(..., description="paid | unpaid")
    paid_date: date | None = None
    is_overdue: bool

    @classmethod
    def build(cls, occ, today: date) -> "OccurrenceData":
        """Собирает ответ из ORM-объекта; today в часовом поясе из .env."""
        return cls(
            id=occ.id,
            recurring_payment_id=occ.recurring_payment_id,
            department_id=occ.department_id,
            title=occ.title,
            amount=occ.amount,
            currency=occ.currency,
            period=occ.period,
            original_due_date=occ.original_due_date,
            due_date=occ.due_date,
            reschedule_reason=occ.reschedule_reason,
            is_paid=occ.is_paid,
            status="paid" if occ.is_paid else "unpaid",
            paid_date=occ.paid_date,
            is_overdue=overdue(occ.due_date, occ.is_paid, occ.paid_date, today),
        )


class OccurrenceUpdate(BaseModel):
    """PATCH /payment-occurrences/{id}.

    - is_paid / paid_date: отметка оплаты и исправление фактической даты
      (user, accountant, admin; срок при этом не меняется).
    - due_date + reschedule_reason: перенос срока (только accountant и admin).
    """
    model_config = {"extra": "forbid"}

    is_paid: bool | None = Field(default=None, description="true - оплачено, false - отмена оплаты")
    paid_date: date | None = Field(default=None, description="Фактическая дата оплаты (по умолчанию сегодня)")
    due_date: date | None = Field(default=None, description="Новый срок оплаты")
    reschedule_reason: str | None = Field(default=None, max_length=500, description="Причина переноса срока")

    @model_validator(mode="after")
    def _validate(self):
        if self.is_paid is None and self.paid_date is None and self.due_date is None:
            raise ValueError("Не указано ни одного поля для изменения")
        if self.is_paid is False and self.paid_date is not None:
            raise ValueError("При отмене оплаты paid_date указывать нельзя")
        if self.due_date is not None and not (self.reschedule_reason or "").strip():
            raise ValueError("При переносе срока нужна причина reschedule_reason")
        return self


class CurrencySummary(BaseModel):
    """Итоги по одной валюте (без конвертации).

    paid: сумма оплаченных периодов; unpaid: сумма неоплаченных;
    overdue: сумма неоплаченных периодов со сроком в прошлом.
    """
    currency: Currency
    paid: Decimal
    unpaid: Decimal
    overdue: Decimal