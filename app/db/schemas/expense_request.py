from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.db.models.enum import Currency, ExpenseStatus, Periodicity


class ExpenseRequestCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    amount: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)
    currency: Currency
    periodicity: Periodicity = Periodicity.MONTHLY
    desired_date: date = Field(..., description="Желаемая дата первой оплаты")
    comment: str | None = Field(default=None, max_length=2000)
    department_id: int | None = Field(
        default=None, description="Только для администратора; остальные подают заявки от своего отдела"
    )


class ExpenseRequestApprove(BaseModel):
    first_due_date: date | None = Field(
        default=None, description="Срок первой оплаты; по умолчанию desired_date из заявки"
    )


class ExpenseRequestReject(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500, description="Причина отказа")


class ExpenseRequestData(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    title: str
    amount: Decimal
    currency: Currency
    periodicity: Periodicity
    desired_date: date
    comment: str | None = None
    department_id: int
    author_id: int | None = None
    status: ExpenseStatus
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None
    reject_reason: str | None = None
    recurring_payment_id: int | None = None
    created_at: datetime