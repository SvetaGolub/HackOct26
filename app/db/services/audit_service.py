from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, User
from app.db.services.access import scope_department


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return value


class AuditService:
    @staticmethod
    def record(
        db: AsyncSession,
        *,
        entity_type: str,
        entity_id: int,
        action: str,
        actor: User | None,
        department_id: int | None,
        old: dict | None = None,
        new: dict | None = None,
    ) -> None:
        """Добавляет запись в историю В ТОЙ ЖЕ транзакции, что и сама операция.

        Не коммитит. entity_id должен быть известен: для новых объектов сначала flush().
        """
        db.add(AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            old_value=_jsonable(old) if old is not None else None,
            new_value=_jsonable(new) if new is not None else None,
            actor_id=actor.id if actor else None,
            actor_email=actor.email if actor else None,
            department_id=department_id,
        ))

    @staticmethod
    async def list_logs(
        db: AsyncSession,
        actor: User,
        *,
        entity_type: str | None = None,
        entity_id: int | None = None,
        action: str | None = None,
        department_id: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        """История: админ видит все отделы, остальные только свой."""
        stmt = scope_department(select(AuditLog), AuditLog, actor, department_id)
        if entity_type:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        if entity_id is not None:
            stmt = stmt.where(AuditLog.entity_id == entity_id)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if date_from:
            stmt = stmt.where(AuditLog.created_at >= datetime.combine(date_from, time.min))
        if date_to:
            stmt = stmt.where(AuditLog.created_at < datetime.combine(date_to + timedelta(days=1), time.min))
        stmt = stmt.order_by(AuditLog.id.desc()).limit(limit).offset(offset)
        return list((await db.execute(stmt)).scalars().all())
