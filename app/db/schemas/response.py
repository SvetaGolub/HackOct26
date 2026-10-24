from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Схема ответа при ошибке (400, 401, 403, 404 и т.д.)."""
    success: bool = Field(default=False, description="Флаг успешности запроса")
    message: str = Field(..., description="Текст ошибки для пользователя")


class MessageResponse(BaseModel):
    """Простой успешный ответ (например, после удаления)."""
    success: bool = Field(default=True, description="Флаг успешности запроса")
    message: str = Field(..., description="Сообщение")