from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.models.enum import ExpenseStatus
from app.db.schemas import (
    ExpenseRequestApprove, ExpenseRequestCreate, ExpenseRequestData, ExpenseRequestReject,
)
from app.db.services import ExpenseService
from app.db.session import get_db

router = APIRouter(prefix="/expense-requests", tags=["Заявки на расходы"])


@router.post("", response_model=ExpenseRequestData, status_code=201)
async def create_request(
    payload: ExpenseRequestCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await ExpenseService.create(db, payload, user)


@router.get("", response_model=list[ExpenseRequestData])
async def list_requests(
    status: ExpenseStatus | None = None,
    department_id: int | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await ExpenseService.list_requests(db, user, status, department_id, limit, offset)


@router.get("/{request_id}", response_model=ExpenseRequestData)
async def get_request(
    request_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await ExpenseService.get(db, request_id, user)


@router.post("/{request_id}/approve", response_model=ExpenseRequestData)
async def approve_request(
    request_id: int,
    payload: ExpenseRequestApprove | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Одобрение (бухгалтер своего отдела или админ): создаёт регулярный платёж и первый период."""
    return await ExpenseService.approve(db, request_id, payload, user)


@router.post("/{request_id}/reject", response_model=ExpenseRequestData)
async def reject_request(
    request_id: int, payload: ExpenseRequestReject,
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    return await ExpenseService.reject(db, request_id, payload, user)
