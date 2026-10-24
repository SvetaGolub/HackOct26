from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.models.enum import UserRole
from app.db.schemas import UserCreate, UserUpdate
from app.db.schemas.access import forbidden, not_found, require_roles
from app.db.services.audit_service import AuditService
from app.db.services.auth_service import AuthService


class UserService:
    """Управление обычными пользователями. Только администратор; системного админа менять нельзя."""

    @staticmethod
    async def _check_unique(db: AsyncSession, *, login: str | None, telegram_id: int | None, exclude_id: int | None = None):
        if login is not None:
            stmt = select(User.id).where(User.login == login)
            if exclude_id is not None:
                stmt = stmt.where(User.id != exclude_id)
            if (await db.execute(stmt)).first():
                raise HTTPException(status_code=400, detail="Пользователь с таким логином уже существует")
        if telegram_id is not None:
            stmt = select(User.id).where(User.telegram_id == telegram_id)
            if exclude_id is not None:
                stmt = stmt.where(User.id != exclude_id)
            if (await db.execute(stmt)).first():
                raise HTTPException(status_code=400, detail="Этот Telegram ID уже привязан к другому пользователю")

<<<<<<< HEAD
    @staticmethod
    async def _require_department(db: AsyncSession, department_id: int | None) -> None:
        if department_id is None:
            return
        if await db.get(Department, department_id) is None:
            raise HTTPException(status_code=404, detail="Отдел не найден")

=======
>>>>>>> 7d3683a (пу пу пу)
    @classmethod
    async def list_users(cls, db: AsyncSession, actor: User, limit: int = 100, offset: int = 0) -> list[User]:
        require_roles(actor, UserRole.ADMIN)
        stmt = select(User).order_by(User.id).limit(limit).offset(offset)
        return list((await db.execute(stmt)).scalars().all())

    @classmethod
    async def create_user(cls, db: AsyncSession, payload: UserCreate, actor: User) -> User:
        """Создаёт только обычного пользователя: админ задаётся через .env."""
        require_roles(actor, UserRole.ADMIN)
        await cls._check_unique(db, login=payload.login, telegram_id=payload.telegram_id)

        user = User(
            login=payload.login,
            password_hash=AuthService.get_password_hash(payload.password),
<<<<<<< HEAD
            full_name=payload.full_name or str(payload.email),
            role=role,
            department_id=payload.department_id,
=======
            full_name=payload.full_name or payload.login,
            role=UserRole.USER,
>>>>>>> 7d3683a (пу пу пу)
            telegram_id=payload.telegram_id,
        )
        db.add(user)
        await db.flush()
        AuditService.record(
            db, entity_type="user", entity_id=user.id, action="create", actor=actor,
            new={"login": user.login, "role": user.role},
        )
        await db.commit()
        await db.refresh(user)
        return user

    @classmethod
    async def update_user(cls, db: AsyncSession, user_id: int, payload: UserUpdate, actor: User) -> User:
        require_roles(actor, UserRole.ADMIN)
        user = await db.get(User, user_id)
        if user is None:
            raise not_found("Пользователь не найден")
        if user.is_system:
            raise forbidden("Учётную запись администратора нельзя изменять")

        data = payload.model_dump(exclude_unset=True)
        if not data:
            raise HTTPException(status_code=400, detail="Нет полей для изменения")

        await cls._check_unique(
            db, login=data.get("login"), telegram_id=data.get("telegram_id"), exclude_id=user.id
        )

        old, new = {}, {}
        for field in ("login", "full_name", "telegram_id"):
            if field in data and data[field] != getattr(user, field):
                old[field], new[field] = getattr(user, field), data[field]
                setattr(user, field, data[field])
        if data.get("password"):
            user.password_hash = AuthService.get_password_hash(data["password"])
            new["password"] = "changed"  # сам пароль и хеш в историю не пишем

        if new:
            AuditService.record(
                db, entity_type="user", entity_id=user.id, action="update", actor=actor, old=old, new=new,
            )
        await db.commit()
        await db.refresh(user)
        return user

    @classmethod
    async def delete_user(cls, db: AsyncSession, user_id: int, actor: User) -> None:
        require_roles(actor, UserRole.ADMIN)
        user = await db.get(User, user_id)
        if user is None:
            raise not_found("Пользователь не найден")
        if user.is_system or user.id == actor.id:
            raise forbidden("Эту учётную запись удалить нельзя")
        AuditService.record(
            db, entity_type="user", entity_id=user.id, action="delete", actor=actor,
            old={"login": user.login, "role": user.role},
        )
        await db.delete(user)
        await db.commit()