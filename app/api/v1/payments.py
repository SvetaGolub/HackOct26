from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import User
from app.api.deps import get_current_user
from app.db.schemas import *
from app.db.services import *

router = APIRouter(tags=["Регулярные платежи и оплаты"])

@router.get("/recurring-payments", response_model=PaymentListResponse)
async def get_recurring_payments(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получение списка регулярных платежей."""
    payments = await PaymentService.get_all_payments(db, current_user)
    return PaymentListResponse(payments=payments)

@router.post("/recurring-payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_recurring_payment(
    payment_in: PaymentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Создание регулярного платежа (Только Администратор)."""
    payment = await PaymentService.create_payment(db, payment_in, current_user)
    return PaymentResponse(payment=payment)

@router.delete("/recurring-payments/{id}", response_model=dict)
async def delete_recurring_payment(
    id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Прекращение регулярного платежа и его напоминаний с сохранением истории."""
    await PaymentService.delete_payment(db, id, current_user)
    return {"success": True, "message": f"Регулярный платеж ID {id} успешно прекращен"}

@router.get("/payment-occurrences", response_model=PaymentListResponse)
async def get_payment_occurrences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получение списка платежей (оплаченные и просроченные)."""
    # Использует ту же выборку или фильтрацию по необходимости
    payments = await PaymentService.get_all_payments(db, current_user)
    return PaymentListResponse(payments=payments)

@router.get("/payment-occurrences/{id}", response_model=PaymentResponse)
async def get_specific_payment(
    id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получение конкретного платежа по его ID."""
    # Быстрый инлайн вызов сервиса для получения одной записи
    payment = await PaymentService.get_payment_by_id(db, id, current_user)
    return PaymentResponse(payment=payment)

@router.patch("/payment-occurrences/{id}", response_model=PaymentResponse)
async def update_payment_occurrence(
    id: int,
    update_data: PaymentUpdateStatus,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Подтверждение или отмена оплаты, исправление фактической даты оплаты."""
    payment = await PaymentService.update_payment_status(db, id, update_data, current_user)
    return PaymentResponse(payment=payment)
