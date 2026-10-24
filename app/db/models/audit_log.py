from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.database import Base


class AuditLog(Base):
    """История изменений. Пишется из сервисов одним хелпером.

    user/accountant видят записи своего department_id, admin видит все.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_dept_created", "department_id", "created_at"),
        Index("ix_audit_entity", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # expense_request / occurrence / recurring_payment / user
    entity_id: Mapped[int] = mapped_column(nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # create / approve / reject / mark_paid / unmark_paid / fix_paid_date / reschedule / delete
    old_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Снимок email: автор остаётся известным после удаления пользователя
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, {self.entity_type}#{self.entity_id} {self.action})>"
