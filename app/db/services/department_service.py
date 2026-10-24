from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Department, User
from app.db.models.enum import UserRole
from app.db.schemas import DepartmentCreate
from app.db.schemas.access import is_admin, require_roles
from app.db.services.audit_service import AuditService


class DepartmentService:
    @staticmethod
    async def list_departments(db: AsyncSession, actor: User) -> list[Department]:
        """Админ видит все отделы, остальные только свой."""
        stmt = select(Department).order_by(Department.name)
        if not is_admin(actor):
            if actor.department_id is None:
                return []
            stmt = stmt.where(Department.id == actor.department_id)
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def create(db: AsyncSession, payload: DepartmentCreate, actor: User) -> Department:
        require_roles(actor, UserRole.ADMIN)
        name = payload.name.strip()
        exists = (await db.execute(select(Department).where(Department.name == name))).scalar_one_or_none()
        if exists:
            raise HTTPException(status_code=400, detail="Отдел с таким названием уже существует")
        dept = Department(name=name)
        db.add(dept)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=400, detail="Отдел с таким названием уже существует")
        AuditService.record(
            db, entity_type="department", entity_id=dept.id, action="create",
            actor=actor, department_id=dept.id, new={"name": name},
        )
        await db.commit()
        await db.refresh(dept)
        return dept