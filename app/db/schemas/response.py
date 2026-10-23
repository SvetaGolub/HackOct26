from pydantic import Field, BaseModel


class ErrorResponse(BaseModel):
    """Схема ответа при ошибке (400, 401, 403, 404 и т.д.)."""
    success: bool = Field(default=False, description="Флаг успешности запроса")
    message: str = Field(..., description="Текст ошибки для пользователя")