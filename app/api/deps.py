from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.models.enum import UserRole
from app.db.schemas.access import require_roles
from app.db.services import AuthService
from app.db.session import get_db

# auto_error=False: без токена всегда отвечаем 401 (а не 403, как в старых версиях FastAPI)
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Валидация JWT и загрузка пользователя из БД (роль всегда актуальная)."""
    if credentials is None:
        raise HTTPException(
            status_code=401, detail="Требуется авторизация", headers={"WWW-Authenticate": "Bearer"}
        )
    return await AuthService.get_current_user(db, credentials.credentials)


async def require_admin(user: User = Depends(get_current_user)) -> User:
    require_roles(user, UserRole.ADMIN)
    return user