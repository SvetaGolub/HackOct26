from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PaymentOccurrence, User
from app.db.schemas import *
from app.db.services.payment_service import PaymentService
from app.db.services.schedule import today_local

# ВНИМАНИЕ: подставьте свои пути к этим двум зависимостям
from app.db.session import get_db
from app.api.deps import get_current_user

router = APIRouter(tags=["payments"])


def to_occurrence_data(occ: PaymentOccurrence) -> OccurrenceData:
    return OccurrenceData(
        id=occ.id,
        recurring_payment_id=occ.recurring_payment_id,
        title=occ.title,
        amount=occ.amount,
        currency=occ.currency,
        due_date=occ.due_date,
        is_paid=occ.is_paid,
        status="paid" if occ.is_paid else "unpaid",
        paid_date=occ.paid_date,
        is_overdue=occ.is_overdue(today_local()),
    )


@router.get("/recurring-payments", response_model=list[RecurringPaymentData])
async def list_recurring(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await PaymentService.list_recurring(db)


@router.post("/recurring-payments", response_model=RecurringPaymentData, status_code=201)
async def create_recurring(
    data: RecurringPaymentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await PaymentService.create_recurring(db, data, user)


@router.delete("/recurring-payments/{recurring_id}", status_code=204)
async def delete_recurring(
    recurring_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await PaymentService.delete_recurring(db, recurring_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/payment-occurrences", response_model=list[OccurrenceData])
async def list_occurrences(
    status_filter: str | None = Query(default=None, alias="status", pattern="^(paid|unpaid|overdue)$"),
    currency: str | None = Query(default=None, pattern="^(RUB|USD|EUR)$"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    occs = await PaymentService.list_occurrences(db, status_filter, currency)
    return [to_occurrence_data(o) for o in occs]


@router.get("/payment-occurrences/{occurrence_id}", response_model=OccurrenceData)
async def get_occurrence(
    occurrence_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return to_occurrence_data(await PaymentService.get_occurrence(db, occurrence_id))


@router.patch("/payment-occurrences/{occurrence_id}", response_model=OccurrenceData)
async def update_occurrence(
    occurrence_id: int,
    data: OccurrenceUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    occ = await PaymentService.update_occurrence(db, occurrence_id, data, user)
    return to_occurrence_data(occ)


@router.get("/payments/summary", response_model=list[CurrencySummary])
async def payments_summary(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await PaymentService.summary(db)