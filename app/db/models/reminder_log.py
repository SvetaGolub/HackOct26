from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.database import Base


class ReminderLog(Base):
    """Факт отправки напоминания конкретному пользователю по конкретному периоду.

    Уникальность (occurrence_id, user_id) защищает от дублей.
    При переносе due_date записи периода удаляются, чтобы напоминание
    пришло заново перед новой датой.
    """

    __tablename__ = "reminder_logs"
    __table_args__ = (
        UniqueConstraint("occurrence_id", "user_id", name="uq_reminder_once"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    occurrence_id: Mapped[int] = mapped_column(
        ForeignKey("payment_occurrences.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )