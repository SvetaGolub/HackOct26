from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Department, User
from app.db.models.enum import UserRole
from app.db.schemas import UserCreate, UserUpdate
from app.db.services.access import forbidden, not_found, require_roles
from app.db.services.audit_service import AuditService
from app.db.services.auth_service import AuthService

_ASSIGNABLE = {UserRole.USER, UserRole.ACCOUNTANT}


class UserService:
    """Управление пользователями. Только администратор; системного админа менять нельзя."""

    @staticmethod
    async def _reload(db: AsyncSession, user: User) -> User:
        await db.refresh(user)
        await db.refresh(user, ["department"])
        return user

    @staticmethod
    async def _check_unique(db: AsyncSession, *, email: str | None, telegram_id: int | None, exclude_id: int | None = None):
        if email is not None:
            stmt = select(User.id).where(User.email == email)
            if exclude_id is not None:
                stmt = stmt.where(User.id != exclude_id)
            if (await db.execute(stmt)).first():
                raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")
        if telegram_id is not None:
            stmt = select(User.id).where(User.telegram_id == telegram_id)
            if exclude_id is not None:
                stmt = stmt.where(User.id != exclude_id)
            if (await db.execute(stmt)).first():
                raise HTTPException(status_code=400, detail="Этот Telegram ID уже привязан к другому пользователю")

    @staticmethod
    async def _require_department(db: AsyncSession, department_id: int | None) -> None:
        if department_id is None:
            raise HTTPException(status_code=400, detail="Для пользователя и бухгалтера нужен отдел")
        if await db.get(Department, department_id) is None:
            raise HTTPException(status_code=404, detail="Отдел не найден")

    @classmethod
    async def list_users(
        cls, db: AsyncSession, actor: User, department_id: int | None = None, limit: int = 100, offset: int = 0
    ) -> list[User]:
        require_roles(actor, UserRole.ADMIN)
        stmt = select(User).order_by(User.id).limit(limit).offset(offset)
        if department_id is not None:
            stmt = stmt.where(User.department_id == department_id)
        return list((await db.execute(stmt)).scalars().all())

    @classmethod
    async def create_user(cls, db: AsyncSession, payload: UserCreate, actor: User) -> User:
        require_roles(actor, UserRole.ADMIN)
        role = UserRole(payload.role)
        if role not in _ASSIGNABLE:  # админа через API создать нельзя
            raise HTTPException(status_code=400, detail="Недопустимая роль")
        await cls._require_department(db, payload.department_id)
        await cls._check_unique(db, email=payload.email, telegram_id=payload.telegram_id)

        user = User(
            email=payload.email,
            password_hash=AuthService.get_password_hash(payload.password),
            full_name=payload.full_name,
            role=role,
            department_id=payload.department_id,
            telegram_id=payload.telegram_id,
        )
        db.add(user)
        await db.flush()
        AuditService.record(
            db, entity_type="user", entity_id=user.id, action="create", actor=actor,
            department_id=user.department_id,
            new={"email": user.email, "role": role, "department_id": user.department_id},
        )
        await db.commit()
        return await cls._reload(db, user)

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

        new_role = UserRole(data["role"]) if data.get("role") else user.role
        new_dept = data["department_id"] if "department_id" in data else user.department_id
        await cls._require_department(db, new_dept)
        await cls._check_unique(
            db, email=data.get("email"), telegram_id=data.get("telegram_id"), exclude_id=user.id
        )

        old, new = {}, {}
        for field in ("email", "full_name", "telegram_id"):
            if field in data and data[field] != getattr(user, field):
                old[field], new[field] = getattr(user, field), data[field]
                setattr(user, field, data[field])
        if new_role != user.role:
            old["role"], new["role"] = user.role, new_role
            user.role = new_role
        if new_dept != user.department_id:
            old["department_id"], new["department_id"] = user.department_id, new_dept
            user.department_id = new_dept
        if data.get("password"):
            user.password_hash = AuthService.get_password_hash(data["password"])
            new["password"] = "changed"  # сам пароль и хеш в историю не пишем

        if new:
            AuditService.record(
                db, entity_type="user", entity_id=user.id, action="update", actor=actor,
                department_id=user.department_id, old=old, new=new,
            )
        await db.commit()
        return await cls._reload(db, user)

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
            department_id=user.department_id, old={"email": user.email, "role": user.role},
        )
        await db.delete(user)
        await db.commit()