from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.models.enum import Currency
from app.db.schemas import (
    CurrencySummary, OccurrenceData, OccurrenceStatusFilter, OccurrenceUpdate,
    RecurringPaymentCreate, RecurringPaymentData,
)
from app.db.services import PaymentService
from app.db.session import get_db

router = APIRouter(tags=["Платежи"])


@router.get("/recurring-payments", response_model=list[RecurringPaymentData])
async def list_recurring(
<<<<<<< HEAD
    department_id: int | None = Query(None, description="Необязательный фильтр по отделу"),
=======
>>>>>>> 7d3683a (пу пу пу)
    include_inactive: bool = False,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Общий список регулярных платежей."""
    return await PaymentService.list_recurring(db, user, include_inactive, limit, offset)


@router.post("/recurring-payments", response_model=RecurringPaymentData, status_code=201)
async def create_recurring(
    data: RecurringPaymentCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    """Создание регулярного платежа (только администратор)."""
    return await PaymentService.create_recurring(db, data, user)


@router.delete("/recurring-payments/{recurring_id}", status_code=204)
async def delete_recurring(
    recurring_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    """Прекращение платежа и его напоминаний с сохранением истории (только админ)."""
    await PaymentService.delete_recurring(db, recurring_id, user)
    return Response(status_code=204)


@router.get("/payment-occurrences", response_model=list[OccurrenceData])
async def list_occurrences(
    status: OccurrenceStatusFilter | None = None,
    currency: Currency | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await PaymentService.list_occurrences(
        db, user, status=status, currency=currency,
        date_from=date_from, date_to=date_to, limit=limit, offset=offset,
    )


@router.get("/payment-occurrences/{occurrence_id}", response_model=OccurrenceData)
async def get_occurrence(
    occurrence_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await PaymentService.get_occurrence(db, occurrence_id, user)


@router.patch("/payment-occurrences/{occurrence_id}", response_model=OccurrenceData)
async def update_occurrence(
    occurrence_id: int, data: OccurrenceUpdate,
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    """Отметка или отмена оплаты и исправление фактической даты."""
    return await PaymentService.update_occurrence(db, occurrence_id, data, user)


@router.get("/payments/summary", response_model=list[CurrencySummary])
async def payments_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Итоги отдельно по RUB, USD и EUR (без конвертации)."""
    return await PaymentService.summary(db, user)