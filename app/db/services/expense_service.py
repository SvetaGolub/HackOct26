from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ExpenseRequest, RecurringPayment, User
from app.db.models.enum import ExpenseStatus, UserRole
from app.db.schemas import ExpenseRequestApprove, ExpenseRequestCreate, ExpenseRequestReject
from app.db.schemas.access import (
    can_access_department, forbidden, is_admin, not_found, require_roles,
    resolve_department, scope_department,
)
from app.db.services.audit_service import AuditService
from app.db.services.schedule import ensure_occurrences

_REVIEWERS = (UserRole.ADMIN, UserRole.ACCOUNTANT)


class ExpenseService:
    @classmethod
    async def create(cls, db: AsyncSession, payload: ExpenseRequestCreate, actor: User) -> ExpenseRequest:
        """Заявку может подать любая роль, от своего отдела (админ указывает отдел явно)."""
        department_id = await resolve_department(db, actor, payload.department_id)
        req = ExpenseRequest(
            title=payload.title.strip(),
            amount=payload.amount,
            currency=payload.currency,
            periodicity=payload.periodicity,
            desired_date=payload.desired_date,
            comment=payload.comment,
            department_id=department_id,
            author_id=actor.id,
            status=ExpenseStatus.PENDING,
        )
        db.add(req)
        await db.flush()
        AuditService.record(
            db, entity_type="expense_request", entity_id=req.id, action="create", actor=actor,
            department_id=department_id,
            new={"title": req.title, "amount": req.amount, "currency": req.currency,
                 "periodicity": req.periodicity, "desired_date": req.desired_date},
        )
        await db.commit()
        await db.refresh(req)
        return req

    @staticmethod
    async def list_requests(
        db: AsyncSession, actor: User, status: ExpenseStatus | None = None,
        department_id: int | None = None, limit: int = 100, offset: int = 0,
    ) -> list[ExpenseRequest]:
        stmt = scope_department(select(ExpenseRequest), ExpenseRequest, actor, department_id)
        if status is not None:
            stmt = stmt.where(ExpenseRequest.status == status)
        stmt = stmt.order_by(ExpenseRequest.id.desc()).limit(limit).offset(offset)
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def get(db: AsyncSession, request_id: int, actor: User) -> ExpenseRequest:
        req = await db.get(ExpenseRequest, request_id)
        if req is None or not can_access_department(actor, req.department_id):
            raise not_found("Заявка не найдена")
        return req

    @classmethod
    async def _load_for_review(cls, db: AsyncSession, request_id: int, actor: User) -> ExpenseRequest:
        require_roles(actor, *_REVIEWERS)
        # блокировка строки: две одновременные проверки одной заявки невозможны
        req = (await db.execute(
            select(ExpenseRequest).where(ExpenseRequest.id == request_id).with_for_update()
        )).scalar_one_or_none()
        if req is None or not can_access_department(actor, req.department_id):
            raise not_found("Заявка не найдена")
        if req.status != ExpenseStatus.PENDING:
            raise HTTPException(status_code=409, detail="Заявка уже рассмотрена")
        if req.author_id == actor.id and not is_admin(actor):
            raise forbidden("Нельзя рассматривать собственную заявку")
        return req

    @classmethod
    async def approve(
        cls, db: AsyncSession, request_id: int, payload: ExpenseRequestApprove | None, actor: User
    ) -> ExpenseRequest:
        """Одобрение: одна транзакция на заявку, регулярный платёж, первый период и историю."""
        req = await cls._load_for_review(db, request_id, actor)
        first_due = (payload.first_due_date if payload and payload.first_due_date else req.desired_date)

        rp = RecurringPayment(
            title=req.title,
            amount=req.amount,
            currency=req.currency,
            periodicity=req.periodicity,
            first_due_date=first_due,
            anchor_day=first_due.day,
            department_id=req.department_id,
            created_by=actor.id,
        )
        db.add(rp)
        await db.flush()
        await ensure_occurrences(db, rp)

        req.status = ExpenseStatus.APPROVED
        req.reviewed_by = actor.id
        req.reviewed_at = datetime.now(timezone.utc)
        req.recurring_payment_id = rp.id

        AuditService.record(
            db, entity_type="expense_request", entity_id=req.id, action="approve", actor=actor,
            department_id=req.department_id,
            old={"status": ExpenseStatus.PENDING},
            new={"status": ExpenseStatus.APPROVED, "recurring_payment_id": rp.id, "first_due_date": first_due},
        )
        AuditService.record(
            db, entity_type="recurring_payment", entity_id=rp.id, action="create", actor=actor,
            department_id=req.department_id,
            new={"title": rp.title, "amount": rp.amount, "currency": rp.currency,
                 "periodicity": rp.periodicity, "first_due_date": first_due, "expense_request_id": req.id},
        )
        await db.commit()
        await db.refresh(req)
        return req

    @classmethod
    async def reject(
        cls, db: AsyncSession, request_id: int, payload: ExpenseRequestReject, actor: User
    ) -> ExpenseRequest:
        req = await cls._load_for_review(db, request_id, actor)
        reason = payload.reason.strip()
        req.status = ExpenseStatus.REJECTED
        req.reviewed_by = actor.id
        req.reviewed_at = datetime.now(timezone.utc)
        req.reject_reason = reason
        AuditService.record(
            db, entity_type="expense_request", entity_id=req.id, action="reject", actor=actor,
            department_id=req.department_id,
            old={"status": ExpenseStatus.PENDING},
            new={"status": ExpenseStatus.REJECTED, "reject_reason": reason},
        )
        await db.commit()
        await db.refresh(req)
        return req