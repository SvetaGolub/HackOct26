from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditLogData(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    entity_type: str
    entity_id: int
    action: str
    old_value: dict[str, Any] | None = None
    new_value: dict[str, Any] | None = None
    actor_id: int | None = None
    actor_email: str | None = None
    department_id: int | None = None
    created_at: datetime