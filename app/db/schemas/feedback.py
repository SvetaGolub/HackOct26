from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.db.models.enum import Currency, Periodicity


class FeedbackCreate(BaseModel):
    employee: str = Field(..., min_length=1, max_length=255)
    department: str = Field(..., min_length=1, max_length=255)
    request: str = Field(..., min_length=1, max_length=5000)
    amount: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)
    currency: Currency
    due_date: date
    periodicity: Periodicity
