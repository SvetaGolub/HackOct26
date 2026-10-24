from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.schemas import FeedbackCreate, MessageResponse
from app.db.services.audit_service import AuditService
from app.db.session import get_db

router = APIRouter(tags=["Обратная связь"])


@router.post("/feedback", response_model=MessageResponse, status_code=201)
async def submit_feedback(
    payload: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    AuditService.record(
        db,
        entity_type="feedback",
        entity_id=user.id,
        action="submit",
        actor=user,
        new=payload.model_dump(mode="json"),
    )
    await db.commit()
    return MessageResponse(message="Обращение отправлено администратору")
