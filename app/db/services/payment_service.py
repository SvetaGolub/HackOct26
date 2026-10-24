from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import and_, case, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import PaymentOccurrence, RecurringPayment, ReminderLog, User
from app.db.models.enum import Currency, UserRole
from app.db.schemas import (
    CurrencySummary, OccurrenceData, OccurrenceStatusFilter, OccurrenceUpdate,
    RecurringPaymentCreate,
)
from app.db.services.access import (
    can_access_department, forbidden, is_staff, not_found, require_roles,
    resolve_department, scope_department,
)
from app.db.services.audit_service import AuditService
from app.db.services.schedule import ensure_occurrences, today_local


def overdue_condition(today: date):
    """SQL-аналог overdue(): оплачено позже срока или не оплачено и срок прошёл."""
    O = PaymentOccurrence
    return or_(
        and_(O.is_paid.is_(True), O.paid_date > O.due_date),
        and_(O.is_paid.is_(False), O.due_date < today),
    )


class PaymentService:
    # ---------- регулярные платежи ----------

    @classmethod
    async def create_recurring(cls, db: AsyncSession, payload: RecurringPaymentCreate, actor: User) -> RecurringPayment:
        """Создание регулярного платежа напрямую: администратор (любой отдел) или бухгалтер (свой)."""
        require_roles(actor, UserRole.ADMIN, UserRole.ACCOUNTANT)
        department_id = await resolve_department(db, actor, payload.department_id)

        rp = RecurringPayment(
            title=payload.title.strip(),
            amount=payload.amount,
            currency=payload.currency,
            periodicity=payload.periodicity,
            first_due_date=payload.first_due_date,
            anchor_day=payload.first_due_date.day,
            department_id=department_id,
            created_by=actor.id,
        )
        db.add(rp)
        await db.flush()
        await ensure_occurrences(db, rp)
        AuditService.record(
            db, entity_type="recurring_payment", entity_id=rp.id, action="create", actor=actor,
            department_id=department_id,
            new={"title": rp.title, "amount": rp.amount, "currency": rp.currency,
                 "periodicity": rp.periodicity, "first_due_date": rp.first_due_date},
        )
        await db.commit()
        await db.refresh(rp)
        return rp

    @staticmethod
    async def list_recurring(
        db: AsyncSession, actor: User, department_id: int | None = None,
        include_inactive: bool = False, limit: int = 100, offset: int = 0,
    ) -> list[RecurringPayment]:
        stmt = scope_department(select(RecurringPayment), RecurringPayment, actor, department_id)
        if not include_inactive:
            stmt = stmt.where(RecurringPayment.is_active.is_(True))
        stmt = stmt.order_by(RecurringPayment.id).limit(limit).offset(offset)
        return list((await db.execute(stmt)).scalars().all())

    @classmethod
    async def delete_recurring(cls, db: AsyncSession, recurring_id: int, actor: User) -> None:
        """Прекращение платежа (только админ): мягкое удаление.

        Оплаченные и просроченные периоды остаются в истории, будущие неоплаченные
        удаляются вместе с их напоминаниями; новые периоды больше не создаются.
        """
        require_roles(actor, UserRole.ADMIN)
        rp = (await db.execute(
            select(RecurringPayment).where(RecurringPayment.id == recurring_id).with_for_update()
        )).scalar_one_or_none()
        if rp is None:
            raise not_found("Регулярный платёж не найден")
        if not rp.is_active:
            raise HTTPException(status_code=409, detail="Платёж уже прекращён")

        today = today_local()
        rp.is_active = False
        rp.deleted_at = func.now()
        await db.execute(
            delete(PaymentOccurrence).where(
                PaymentOccurrence.recurring_payment_id == rp.id,
                PaymentOccurrence.is_paid.is_(False),
                PaymentOccurrence.due_date >= today,
            )
        )
        AuditService.record(
            db, entity_type="recurring_payment", entity_id=rp.id, action="delete", actor=actor,
            department_id=rp.department_id, old={"is_active": True}, new={"is_active": False},
        )
        await db.commit()

    # ---------- периоды оплаты ----------

    @classmethod
    async def list_occurrences(
        cls, db: AsyncSession, actor: User, *,
        status: OccurrenceStatusFilter | None = None,
        currency: Currency | None = None,
        department_id: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[OccurrenceData]:
        today = today_local()
        O = PaymentOccurrence
        stmt = scope_department(select(O), O, actor, department_id)
        if status == OccurrenceStatusFilter.PAID:
            stmt = stmt.where(O.is_paid.is_(True))
        elif status == OccurrenceStatusFilter.UNPAID:
            stmt = stmt.where(O.is_paid.is_(False))
        elif status == OccurrenceStatusFilter.OVERDUE:
            stmt = stmt.where(overdue_condition(today))
        if currency is not None:
            stmt = stmt.where(O.currency == currency)
        if date_from:
            stmt = stmt.where(O.due_date >= date_from)
        if date_to:
            stmt = stmt.where(O.due_date <= date_to)
        stmt = stmt.order_by(O.due_date.asc(), O.id.asc()).limit(limit).offset(offset)
        rows = (await db.execute(stmt)).scalars().all()
        return [OccurrenceData.build(o, today) for o in rows]

    @staticmethod
    async def _load_occurrence(db: AsyncSession, occurrence_id: int, actor: User, for_update: bool = False):
        stmt = (
            select(PaymentOccurrence)
            .options(selectinload(PaymentOccurrence.recurring_payment))
            .where(PaymentOccurrence.id == occurrence_id)
        )
        if for_update:
            stmt = stmt.with_for_update()
        occ = (await db.execute(stmt)).scalar_one_or_none()
        # чужой отдел неотличим от несуществующего объекта
        if occ is None or not can_access_department(actor, occ.department_id):
            raise not_found("Платёж не найден")
        return occ

    @classmethod
    async def get_occurrence(cls, db: AsyncSession, occurrence_id: int, actor: User) -> OccurrenceData:
        occ = await cls._load_occurrence(db, occurrence_id, actor)
        return OccurrenceData.build(occ, today_local())

    @classmethod
    async def update_occurrence(
        cls, db: AsyncSession, occurrence_id: int, payload: OccurrenceUpdate, actor: User
    ) -> OccurrenceData:
        """Отметка/отмена оплаты, исправление фактической даты, перенос срока.

        Права: оплата и фактическая дата доступны всем ролям в пределах своего отдела;
        перенос срока (due_date) только бухгалтеру и админу. Проверки здесь, а не в роутере,
        поэтому они действуют для любого клиента API.
        """
        if payload.due_date is not None and not is_staff(actor):
            raise forbidden("Переносить срок может только бухгалтер")

        occ = await cls._load_occurrence(db, occurrence_id, actor, for_update=True)
        rp = occ.recurring_payment
        today = today_local()
        dept = occ.department_id
        changed = False

        def audit(action: str, old: dict, new: dict) -> None:
            AuditService.record(
                db, entity_type="payment_occurrence", entity_id=occ.id, action=action,
                actor=actor, department_id=dept, old=old, new=new,
            )

        # --- оплата ---
        if payload.is_paid is False:
            if occ.is_paid:
                audit("unmark_paid", {"is_paid": True, "paid_date": occ.paid_date}, {"is_paid": False, "paid_date": None})
                occ.is_paid, occ.paid_date, occ.paid_by = False, None, None
                changed = True
        elif payload.is_paid is True or payload.paid_date is not None:
            if payload.is_paid is None and not occ.is_paid:
                raise HTTPException(status_code=400, detail="Нельзя указать дату оплаты для неоплаченного периода")
            new_date = payload.paid_date or (occ.paid_date if occ.is_paid else today)
            if new_date > today:
                raise HTTPException(status_code=400, detail="Дата оплаты не может быть в будущем")
            if not occ.is_paid:
                audit("mark_paid", {"is_paid": False, "paid_date": None}, {"is_paid": True, "paid_date": new_date})
                occ.is_paid, occ.paid_date, occ.paid_by = True, new_date, actor.id
                changed = True
            elif new_date != occ.paid_date:
                audit("fix_paid_date", {"paid_date": occ.paid_date}, {"paid_date": new_date})
                occ.paid_date = new_date  # срок не меняется, просрочка пересчитывается сама
                changed = True

        # --- перенос срока ---
        if payload.due_date is not None and payload.due_date != occ.due_date:
            if not rp.is_active:
                raise HTTPException(status_code=409, detail="Платёж прекращён, срок переносить нельзя")
            reason = payload.reschedule_reason.strip()
            audit(
                "reschedule",
                {"due_date": occ.due_date, "reschedule_reason": occ.reschedule_reason},
                {"due_date": payload.due_date, "reschedule_reason": reason},
            )
            occ.due_date = payload.due_date
            occ.rescheduled_by = actor.id
            occ.reschedule_reason = reason
            # новый срок: напоминание должно прийти заново
            await db.execute(delete(ReminderLog).where(ReminderLog.occurrence_id == occ.id))
            changed = True

        if changed:
            await db.commit()
            await db.refresh(occ)
        return OccurrenceData.build(occ, today)

    # ---------- итоги ----------

    @staticmethod
    async def summary(db: AsyncSession, actor: User, department_id: int | None = None) -> list[CurrencySummary]:
        """Итоги отдельно по каждой валюте (без конвертации); всегда три валюты.

        overdue: неоплаченные периоды со сроком в прошлом (текущая задолженность).
        """
        today = today_local()
        O = PaymentOccurrence
        stmt = scope_department(
            select(
                O.currency,
                func.coalesce(func.sum(case((O.is_paid.is_(True), O.amount), else_=0)), 0),
                func.coalesce(func.sum(case((O.is_paid.is_(False), O.amount), else_=0)), 0),
                func.coalesce(func.sum(case((and_(O.is_paid.is_(False), O.due_date < today), O.amount), else_=0)), 0),
            ),
            O, actor, department_id,
        ).group_by(O.currency)
        found = {row[0]: row for row in (await db.execute(stmt)).all()}

        result = []
        for cur in Currency:
            row = found.get(cur)
            result.append(CurrencySummary(
                currency=cur,
                paid=Decimal(row[1]) if row else Decimal("0"),
                unpaid=Decimal(row[2]) if row else Decimal("0"),
                overdue=Decimal(row[3]) if row else Decimal("0"),
            ))
        return result