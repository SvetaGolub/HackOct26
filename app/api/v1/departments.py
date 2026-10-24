from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.schemas import DepartmentCreate, DepartmentData
from app.db.services import DepartmentService
from app.db.session import get_db

router = APIRouter(tags=["Отделы"])


@router.get("/departments", response_model=list[DepartmentData])
async def list_departments(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Админ видит все отделы, остальные только свой."""
    return await DepartmentService.list_departments(db, user)


@router.post("/departments", response_model=DepartmentData, status_code=201)
async def create_department(
    payload: DepartmentCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await DepartmentService.create(db, payload, user)
