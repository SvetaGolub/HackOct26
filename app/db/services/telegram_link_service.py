import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TelegramLinkCode, User
from app.db.services.audit_service import AuditService

CODE_TTL_MINUTES = 10
CODE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
CODE_LENGTH = 10


def _hash(code: str) -> str:
    return hashlib.sha256(code.strip().encode()).hexdigest()


def _utcnow() -> datetime:
    """Naive UTC: колонка expires_at хранится без часового пояса."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TelegramLinkService:
    @classmethod
    async def create_code(cls, db: AsyncSession, telegram_id: int) -> tuple[str, int]:
        """Выдаёт код для Telegram-аккаунта; предыдущие и просроченные коды удаляются."""
        now = _utcnow()
        await db.execute(delete(TelegramLinkCode).where(
            or_(TelegramLinkCode.telegram_id == telegram_id, TelegramLinkCode.expires_at < now)
        ))
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        db.add(TelegramLinkCode(
            telegram_id=telegram_id,
            code_hash=_hash(code),
            expires_at=now + timedelta(minutes=CODE_TTL_MINUTES),
        ))
        await db.commit()
        return code, CODE_TTL_MINUTES * 60

    @classmethod
    async def consume(cls, db: AsyncSession, code: str, user: User) -> User | None:
        """Привязывает владельца кода к авторизованному пользователю. Код одноразовый."""
        row = (await db.execute(
            select(TelegramLinkCode).where(TelegramLinkCode.code_hash == _hash(code)).with_for_update()
        )).scalar_one_or_none()
        if row is None:
            return None

        telegram_id = row.telegram_id
        expired = row.expires_at < _utcnow()
        await db.delete(row)  # код сгорает в любом случае
        if expired or telegram_id is None or user.id is None:
            await db.commit()
            return None

        # Этот Telegram мог быть привязан к другому аккаунту: переносим привязку
        others = (await db.execute(
            select(User).where(User.telegram_id == telegram_id, User.id != user.id)
        )).scalars().all()
        for other in others:
            other.telegram_id = None
        await db.flush()  # освобождаем unique до присвоения

        user.telegram_id = telegram_id
        AuditService.record(
            db, entity_type="user", entity_id=user.id, action="telegram_link", actor=user,
            new={"telegram_linked": True},
        )
        await db.commit()
        return user

    @staticmethod
    async def get_user_by_telegram_id(db: AsyncSession, telegram_id: int) -> User | None:
        return (await db.execute(select(User).where(User.telegram_id == telegram_id))).scalar_one_or_none()

    @classmethod
    async def unlink_user(cls, db: AsyncSession, user: User) -> bool:
        """Отвязка из панели."""
        if user.telegram_id is None:
            return False
        user.telegram_id = None
        AuditService.record(
            db, entity_type="user", entity_id=user.id, action="telegram_unlink", actor=user,
            new={"telegram_linked": False},
        )
        await db.commit()
        return True

    @classmethod
    async def unlink_telegram(cls, db: AsyncSession, telegram_id: int) -> bool:
        """Отвязка командой бота."""
        user = (await db.execute(select(User).where(User.telegram_id == telegram_id))).scalar_one_or_none()
        if user is None:
            return False
        return await cls.unlink_user(db, user)