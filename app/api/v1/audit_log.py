from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.schemas import AuditLogData
from app.db.services import AuditService
from app.db.session import get_db

router = APIRouter(tags=["История изменений"])


@router.get("/audit-log", response_model=list[AuditLogData])
async def list_audit_log(
    entity_type: str | None = Query(None, description="auth, recurring_payment, payment_occurrence, user"),
    entity_id: int | None = None,
    action: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Логи авторизации и действий (только администратор)."""
    return await AuditService.list_logs(
        db, user, entity_type=entity_type, entity_id=entity_id, action=action,
        date_from=date_from, date_to=date_to, limit=limit, offset=offset,
    )