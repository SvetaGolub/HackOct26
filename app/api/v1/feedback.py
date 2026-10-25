import logging

from aiogram.exceptions import TelegramAPIError
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import settings
from app.db.models import User
from app.db.models.enum import UserRole
from app.db.schemas import FeedbackCreate, MessageResponse
from app.db.schemas.access import require_roles
from app.db.services.audit_service import AuditService
from app.db.session import get_db
from app.tg_bot.loader import bot

router = APIRouter(tags=["Обратная связь"])
logger = logging.getLogger(__name__)


def _feedback_message(payload: FeedbackCreate, user: User) -> str:
    periodicity = {
        "monthly": "Ежемесячно",
        "weekly": "Еженедельно",
        "yearly": "Ежегодно",
        "daily": "Ежедневно",
        "one_time": "Разовый платёж",
        "custom": f"Раз в {payload.interval_days} дн.",
    }[payload.periodicity.value]
    return (
        "Новое обращение в Invoice Keeper\n"
        f"Пользователь: {user.login}\n"
        f"ФИО: {payload.employee}\n"
        f"Отдел: {payload.department}\n"
        f"Запрос: {payload.request}\n"
        f"Платёж: {payload.amount} {payload.currency.value}\n"
        f"Срок: {payload.due_date:%d.%m.%Y}\n"
        f"Периодичность: {periodicity}"
    )


def _split_telegram_message(message: str) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_length = 0
    for character in message:
        character_length = len(character.encode("utf-16-le")) // 2
        if current_length + character_length > 4000:
            chunks.append("".join(current))
            current = []
            current_length = 0
        current.append(character)
        current_length += character_length
    if current:
        chunks.append("".join(current))
    return chunks


async def _send_feedback(payload: FeedbackCreate, user: User, db: AsyncSession) -> None:
    admins = await db.execute(
        select(User.telegram_id).where(
            User.role == UserRole.ADMIN,
            User.telegram_id.is_not(None),
        )
    )
    recipients = {str(chat_id) for chat_id in admins.scalars().all()}
    configured_chat_id = settings.ADMIN_TELEGRAM_CHAT_ID.strip()
    if configured_chat_id:
        recipients.add(configured_chat_id)
    elif settings.telegram_chat_id is not None:
        recipients.add(str(settings.telegram_chat_id))
    if not recipients:
        raise HTTPException(
            status_code=503,
            detail="Telegram администратора не подключён. Обращение не отправлено.",
        )

    message = _feedback_message(payload, user)
    chunks = _split_telegram_message(message)
    delivered = False
    for chat_id in recipients:
        try:
            for chunk in chunks:
                await bot.send_message(chat_id, chunk)
            delivered = True
        except TelegramAPIError as exc:
            logger.warning("Не удалось доставить обращение в Telegram %s: %s", chat_id, exc)

    if not delivered:
        raise HTTPException(
            status_code=502,
            detail="Не удалось отправить обращение в Telegram. Попробуйте позже.",
        )


@router.post("/feedback", response_model=MessageResponse, status_code=201)
async def submit_feedback(
    payload: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_roles(user, UserRole.USER)
    await _send_feedback(payload, user, db)
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
