import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class AccessLogCreate(BaseModel):
    """Схема для фиксации попытки проверки доступа в системе."""
    user_id: Optional[int] = Field(default=None, description="ID пользователя (если авторизован)")
    result: str = Field(..., max_length=255, description="Результат проверки / действия")

class AccessLogData(BaseModel):
    """Данные лога доступа."""
    model_config = {"from_attributes": True}

    id: int = Field(..., description="ID лога в БД")
    user_id: Optional[int] = Field(None, description="ID пользователя")
    timestamp: datetime = Field(..., description="Дата и время проверки")
    result: str = Field(..., description="Результат проверки")

class AccessLogListResponse(BaseModel):
    """Ответ API со списком логов (для панели администратора)."""
    success: bool = Field(default=True, description="Флаг успешности запроса")
    logs: List[AccessLogData] = Field(..., description="Список логов доступа")