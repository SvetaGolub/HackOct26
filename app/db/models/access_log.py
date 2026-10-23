from datetime import datetime

from sqlalchemy import Integer, ForeignKey, DateTime, func, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base

class AccessLog(Base):
    __tablename__ = "access_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", onupdate="SET NULL"),
        nullable=True,
        index = True
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),#хранит дату и время с учетом часового пояса
        server_default=func.now(),#значение по умолчанию будет генерироваться на стороне самой базы данных. Защищает от рассинхрона времени
        nullable=False,
    )

    result: Mapped[str] = mapped_column(String(255), nullable=False)#Результат проверки

    def __repr__(self) -> str:
         return (
            f"<AccessLog(id={self.id}, user_id={self.user_id}, result={self.result!r})>"
        )