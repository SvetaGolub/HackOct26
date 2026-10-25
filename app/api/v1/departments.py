from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import Department, User
from app.db.models.enum import UserRole
from app.db.schemas import DepartmentCreate, DepartmentData
from app.db.schemas.access import require_roles
from app.db.session import get_db

router = APIRouter(tags=["Отделы"])


@router.get("/departments", response_model=list[DepartmentData])
async def list_departments(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return list((await db.execute(select(Department).order_by(Department.name))).scalars().all())


@router.post("/departments", response_model=DepartmentData, status_code=201)
async def create_department(
    data: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_roles(user, UserRole.ADMIN)
    department = Department(name=data.name)
    db.add(department)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Такой отдел уже существует") from exc
    await db.refresh(department)
    return department


@router.delete("/departments/{department_id}", status_code=204)
async def delete_department(
    department_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_roles(user, UserRole.ADMIN)
    department = await db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=404, detail="Отдел не найден")
    await db.delete(department)
    await db.commit()
    return Response(status_code=204)
