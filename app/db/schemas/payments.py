import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field

from app.db.models.enum import CURRENCY


class PaymentCreate(BaseModel):
    """Схема для добавления регулярного или обычного платежа администратором."""
    user_id: int = Field(..., description="ID ответственного пользователя за платеж")
    description: str = Field(..., max_length=255, description="Назначение платежа (Аренда, подписка и т.д.)")
    status: str = Field(default="Ожидает", max_length=255, description="Статус платежа (Оплачен, Просрочен, Ожидает)")
    sum: Decimal = Field(..., max_digits=10, decimal_places=2, description="Сумма платежа")
    currency: CURRENCY = Field(default=CURRENCY.RUB, description="Валюта платежа")
    due_date: datetime = Field(..., description="Срок оплаты (Дедлайн)")

class PaymentUpdateStatus(BaseModel):
    """Схема для изменения статуса платежа и даты фактической оплаты пользователем."""
    status: str = Field(..., max_length=255, description="Новый статус платежа (например, 'Оплачен')")
    paid_at: Optional[datetime | None] = Field(default=None, description="Дата и время фактической оплаты")

class PaymentData(BaseModel):
    """Данные платежа для отображения в списках."""
    model_config = {"from_attributes": True}

    id: int = Field(..., description="ID платежа в БД")
    user_id: int = Field(..., description="ID ответственного пользователя")
    description: str = Field(..., description="Назначение платежа")
    status: str = Field(..., description="Статус платежа")
    sum: Decimal = Field(..., description="Сумма платежа")
    currency: CURRENCY = Field(..., description="Валюта платежа")
    created_at: datetime = Field(..., description="Время создания записи в системе")
    due_date: datetime = Field(..., description="Срок оплаты (Дедлайн)")
    paid_at: Optional[datetime | None] = Field(None, description="Дата фактической оплаты")

class PaymentResponse(BaseModel):
    """Ответ API при запросе одного платежа."""
    success: bool = Field(default=True, description="Флаг успешности запроса")
    payment: PaymentData

class PaymentListResponse(BaseModel):
    """Ответ API со списком платежей (общий список)."""
    success: bool = Field(default=True, description="Флаг успешности запроса")
    payments: List[PaymentData] = Field(..., description="Список платежей")