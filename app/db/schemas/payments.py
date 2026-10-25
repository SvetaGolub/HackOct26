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
    model_config = {"extra": "forbid"}

    title: str = Field(..., min_length=1, max_length=255)
    amount: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)
    currency: Currency
    first_due_date: date = Field(..., description="Дата ближайшей оплаты")
    periodicity: Periodicity = Periodicity.MONTHLY
    interval_days: int | None = Field(default=None, ge=1, le=36500)
    department: str | None = Field(default=None, max_length=255)
    employee: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _validate_interval(self):
        if self.periodicity == Periodicity.CUSTOM and self.interval_days is None:
            raise ValueError("Для пользовательской периодичности укажите интервал в днях")
        if self.periodicity != Periodicity.CUSTOM and self.interval_days is not None:
            raise ValueError("Интервал в днях допустим только для пользовательской периодичности")
        return self


class RecurringPaymentUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    title: str | None = Field(default=None, min_length=1, max_length=255)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    currency: Currency | None = None
    first_due_date: date | None = None
    periodicity: Periodicity | None = None
    interval_days: int | None = Field(default=None, ge=1, le=36500)
    department: str | None = Field(default=None, max_length=255)
    employee: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _validate(self):
        if not self.model_fields_set:
            raise ValueError("Не указано ни одного поля для изменения")
        for field in ("title", "amount", "currency", "first_due_date", "periodicity"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"Поле {field} не может быть пустым")
        if self.title is not None:
            self.title = self.title.strip()
            if not self.title:
                raise ValueError("Название не может быть пустым")
        if self.periodicity == Periodicity.CUSTOM and (
            "interval_days" not in self.model_fields_set and self.interval_days is None
        ):
            raise ValueError("Для пользовательской периодичности укажите интервал в днях")
        if self.periodicity is not None and self.periodicity != Periodicity.CUSTOM and self.interval_days is not None:
            raise ValueError("Интервал в днях допустим только для пользовательской периодичности")
        for field in ("department", "employee"):
            value = getattr(self, field)
            if value is not None:
                setattr(self, field, value.strip() or None)
        return self


class RecurringPaymentData(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    title: str
    amount: Decimal
    currency: Currency
    periodicity: Periodicity
    interval_days: int | None = None
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
    receipt_name: str | None = None
    reminder_sent: bool = False

    @classmethod
    def build(cls, occ, today: date, reminder_sent: bool = False) -> "OccurrenceData":
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
            receipt_name=occ.receipt_name,
            reminder_sent=reminder_sent or occ.chat_notified_at is not None,
        )


class ReceiptData(BaseModel):
    name: str
    data_url: str


class OccurrenceUpdate(BaseModel):
    """PATCH /payment-occurrences/{id}.

    is_paid / paid_date: отметка оплаты, её отмена и исправление фактической даты
    (user и admin; срок при этом не меняется).
    """
    model_config = {"extra": "forbid"}

    is_paid: bool | None = Field(default=None, description="true - оплачено, false - отмена оплаты")
    paid_date: date | None = Field(default=None, description="Фактическая дата оплаты (по умолчанию сегодня)")
    receipt_name: str | None = Field(default=None, max_length=255)
    receipt_data_url: str | None = Field(default=None, max_length=2_800_000)

    @model_validator(mode="after")
    def _validate(self):
        receipt_fields = {"receipt_name", "receipt_data_url"}
        if receipt_fields.intersection(self.model_fields_set) and not receipt_fields.issubset(self.model_fields_set):
            raise ValueError("Содержимое и имя файла должны изменяться вместе")
        if (self.is_paid is None and self.paid_date is None
                and not receipt_fields.intersection(self.model_fields_set)):
            raise ValueError("Не указано ни одного поля для изменения")
        if self.receipt_data_url:
            allowed = ("data:image/png;base64,", "data:image/jpeg;base64,",
                       "data:image/webp;base64,", "data:application/pdf;base64,")
            if not self.receipt_data_url.startswith(allowed):
                raise ValueError("Разрешены только PNG, JPEG, WEBP и PDF")
            if not self.receipt_name:
                raise ValueError("Укажите имя файла")
        elif self.receipt_name:
            raise ValueError("Имя файла нельзя сохранить без содержимого")
        # paid_date без is_paid — исправление даты уже оплаченного периода (ТЗ)
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