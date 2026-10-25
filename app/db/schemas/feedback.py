from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.db.models.enum import Currency, Periodicity


class FeedbackCreate(BaseModel):
    employee: str = Field(..., min_length=1, max_length=255)
    department: str = Field(..., min_length=1, max_length=255)
    request: str = Field(..., min_length=1, max_length=5000)
    amount: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)
    currency: Currency
    due_date: date
    periodicity: Periodicity
    interval_days: int | None = Field(default=None, ge=1, le=36500)

    @model_validator(mode="after")
    def _validate_interval(self):
        if self.periodicity == Periodicity.CUSTOM and self.interval_days is None:
            raise ValueError("Для пользовательской периодичности укажите интервал в днях")
        if self.periodicity != Periodicity.CUSTOM and self.interval_days is not None:
            raise ValueError("Интервал в днях допустим только для пользовательской периодичности")
        return self
