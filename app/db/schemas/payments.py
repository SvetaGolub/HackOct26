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
    department: str | None = Field(default=None, max_length=255)
    employee: str | None = Field(default=None, max_length=255)


class RecurringPaymentData(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    title: str
    amount: Decimal
    currency: Currency
    periodicity: Periodicity
    first_due_date: date
    department: str | None = None
    employee: str | None = None
    is_active: bool
    deleted_at: datetime | None = None
    created_at: datetime


class OccurrenceData(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    recurring_payment_id: int
    title: str
    amount: Decimal
    currency: Currency
    department: str | None = None
    employee: str | None = None
    period: date
    due_date: date
    is_paid: bool
    status: str = Field(..., description="paid | unpaid")
    paid_date: date | None = None
    overdue: bool

    @classmethod
    def build(cls, occ, today: date) -> "OccurrenceData":
        """Собирает ответ из ORM-объекта; today в часовом поясе из .env."""
        return cls(
            id=occ.id,
            recurring_payment_id=occ.recurring_payment_id,
            title=occ.title,
            amount=occ.amount,
            currency=occ.currency,
            department=occ.department,
            employee=occ.employee,
            period=occ.period,
            due_date=occ.due_date,
            is_paid=occ.is_paid,
            status="paid" if occ.is_paid else "unpaid",
            paid_date=occ.paid_date,
            overdue=overdue(occ.due_date, occ.is_paid, occ.paid_date, today),
        )


class OccurrenceUpdate(BaseModel):
    """PATCH /payment-occurrences/{id}.

    is_paid / paid_date: отметка оплаты, её отмена и исправление фактической даты
    (user и admin; срок при этом не меняется).
    """
    model_config = {"extra": "forbid"}

    is_paid: bool | None = Field(default=None, description="true - оплачено, false - отмена оплаты")
    paid_date: date | None = Field(default=None, description="Фактическая дата оплаты (по умолчанию сегодня)")

    @model_validator(mode="after")
    def _validate(self):
        if self.is_paid is None and self.paid_date is None:
            raise ValueError("Не указано ни одного поля для изменения")
        if self.is_paid is None and self.paid_date is not None:
            raise ValueError("Для указания даты оплаты передайте is_paid=true")
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