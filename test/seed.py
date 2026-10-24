"""Тестовые данные для демо по ТЗ AEZA.

Запуск:  uv run python -m test.seed
Повторный запуск безопасен: если демо-пользователь уже есть, ничего не дублируется.
"""
from __future__ import annotations

import asyncio
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RecurringPayment, User
from app.db.models.enum import Currency, Periodicity, UserRole
from app.db.schemas import OccurrenceUpdate, RecurringPaymentCreate, UserCreate
from app.db.services.auth_service import AuthService
from app.db.services.payment_service import PaymentService
from app.db.services.schedule import today_local
from app.db.services.user_service import UserService
from app.db.session import async_session_maker

DEMO_PASSWORD = "Demo12345"
DEMO_USER_LOGIN = "user@example.com"


async def seed_demo_data(db: AsyncSession) -> bool:
    """Создаёт демо-пользователя и три платежа (RUB / USD / EUR). True — если засеяли."""
    await AuthService.ensure_system_admin(db)
    admin = (await db.execute(select(User).where(User.is_system.is_(True)))).scalar_one()

    existing = (
        await db.execute(select(User).where(User.login == DEMO_USER_LOGIN))
    ).scalar_one_or_none()
    if existing is not None:
        return False

    user = await UserService.create_user(
        db,
        UserCreate(login=DEMO_USER_LOGIN, password=DEMO_PASSWORD, full_name="Демо Пользователь"),
        admin,
    )

    today = today_local()
    payments = [
        RecurringPaymentCreate(
            title="Аренда офиса",
            amount=Decimal("150000.00"),
            currency=Currency.RUB,
            first_due_date=today + timedelta(days=2),
            periodicity=Periodicity.MONTHLY,
        ),
        RecurringPaymentCreate(
            title="Облачный сервер",
            amount=Decimal("80.00"),
            currency=Currency.USD,
            first_due_date=today - timedelta(days=5),
            periodicity=Periodicity.MONTHLY,
        ),
        RecurringPaymentCreate(
            title="Подписка SaaS",
            amount=Decimal("49.00"),
            currency=Currency.EUR,
            first_due_date=today + timedelta(days=10),
            periodicity=Periodicity.MONTHLY,
        ),
    ]
    created: list[RecurringPayment] = []
    for payload in payments:
        created.append(await PaymentService.create_recurring(db, payload, admin))

    # Один период USD уже «оплачен вовремя» для демо статусов
    from app.db.models import PaymentOccurrence

    occ = (
        await db.execute(
            select(PaymentOccurrence)
            .where(PaymentOccurrence.recurring_payment_id == created[1].id)
            .order_by(PaymentOccurrence.due_date.asc())
        )
    ).scalars().first()
    if occ is not None:
        await PaymentService.update_occurrence(
            db,
            occ.id,
            OccurrenceUpdate(is_paid=True, paid_date=occ.due_date),
            user,
        )

    return True


async def _main() -> None:
    async with async_session_maker() as db:
        seeded = await seed_demo_data(db)
        print("demo seeded" if seeded else "demo already present")


if __name__ == "__main__":
    asyncio.run(_main())
