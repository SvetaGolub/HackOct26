from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.database import Base


class AuditLog(Base):
    """Логи авторизации и действий (доп. возможность ТЗ). Пишется из сервисов."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # auth / occurrence / recurring_payment / user
    entity_id: Mapped[int] = mapped_column(nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # login / logout / create / mark_paid / unmark_paid / fix_paid_date / delete
    old_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Снимок логина: автор остаётся известным после удаления пользователя
    actor_login: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, {self.entity_type}#{self.entity_id} {self.action})>"