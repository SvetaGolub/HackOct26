import asyncio
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.database import Base
from app.db.models import Department, PaymentOccurrence, RecurringPayment, User
from app.db.models.enum import Currency, Periodicity
from app.db.services.reminder_service import ReminderService


def test_reminders_match_current_per_user_model_and_deduplicate(acceptance_db):
    async def scenario():
        today = date(2026, 10, 24)
        async with acceptance_db() as db:
            department = (
                await db.execute(select(Department).where(Department.name == "Acceptance"))
            ).scalar_one()
            recipient = (
                await db.execute(select(User).where(User.email == "user@example.com"))
            ).scalar_one()
            assert recipient.telegram_id == 123456789

            async def payment(title, due, *, paid=False, active=True):
                recurring = RecurringPayment(
                    title=title,
                    amount=Decimal("12.50"),
                    currency=Currency.EUR,
                    periodicity=Periodicity.MONTHLY,
                    first_due_date=due,
                    anchor_day=due.day,
                    department_id=department.id,
                    is_active=active,
                )
                db.add(recurring)
                await db.flush()
                occurrence = PaymentOccurrence(
                    recurring_payment_id=recurring.id,
                    department_id=department.id,
                    title=title,
                    amount=recurring.amount,
                    currency=recurring.currency,
                    period=due.replace(day=1),
                    due_date=due,
                    is_paid=paid,
                    paid_date=today if paid else None,
                )
                db.add(occurrence)
                await db.flush()
                return occurrence

            due_in_three_days = await payment("Due in three days", today + timedelta(days=3))
            due_in_four_days = await payment("Outside window", today + timedelta(days=4))
            overdue = await payment("Added late", today - timedelta(days=1))
            await payment("Already paid", today + timedelta(days=1), paid=True)
            await payment("Stopped", today + timedelta(days=1), active=False)
            await db.commit()

            due_in_three_days_id = due_in_three_days.id
            overdue_id = overdue.id
            reminders = await ReminderService.collect(db, today)
            assert {reminder.occurrence_id for reminder in reminders} == {
                due_in_three_days_id,
                overdue_id,
            }
            by_occurrence = {reminder.occurrence_id: reminder for reminder in reminders}
            reminder = by_occurrence[due_in_three_days_id]
            assert reminder.user_id == recipient.id
            assert reminder.telegram_id == recipient.telegram_id
            assert "Due in three days" in reminder.text
            assert "12.50 EUR" in reminder.text
            assert "27.10.2026" in reminder.text

            assert await ReminderService._reserve(
                db, due_in_three_days_id, recipient.id
            ) is True
            assert await ReminderService._reserve(
                db, due_in_three_days_id, recipient.id
            ) is False
            assert due_in_three_days_id not in {
                item.occurrence_id for item in await ReminderService.collect(db, today)
            }
            await ReminderService._release(db, due_in_three_days_id, recipient.id)
            assert due_in_three_days_id in {
                item.occurrence_id for item in await ReminderService.collect(db, today)
            }

    asyncio.run(scenario())


def test_database_keeps_paid_payment_history_after_reopening(tmp_path):
    async def scenario():
        database_url = f"sqlite+aiosqlite:///{(tmp_path / 'acceptance.db').as_posix()}"
        engine = create_async_engine(database_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        due = date(2026, 11, 1)
        async with sessions() as db:
            recurring = RecurringPayment(
                title="Persistent rent",
                amount=Decimal("100.00"),
                currency=Currency.RUB,
                periodicity=Periodicity.MONTHLY,
                first_due_date=due,
                anchor_day=due.day,
            )
            db.add(recurring)
            await db.flush()
            occurrence = PaymentOccurrence(
                recurring_payment_id=recurring.id,
                title=recurring.title,
                amount=recurring.amount,
                currency=recurring.currency,
                period=due.replace(day=1),
                due_date=due,
                is_paid=True,
                paid_date=due,
            )
            db.add(occurrence)
            await db.commit()
            recurring_id = recurring.id
            occurrence_id = occurrence.id
        await engine.dispose()

        reopened_engine = create_async_engine(database_url)
        reopened_sessions = async_sessionmaker(reopened_engine, expire_on_commit=False)
        async with reopened_sessions() as db:
            recurring = await db.get(RecurringPayment, recurring_id)
            occurrence = await db.get(PaymentOccurrence, occurrence_id)
            assert recurring.title == "Persistent rent"
            assert occurrence.due_date == due
            assert occurrence.is_paid is True
            assert occurrence.paid_date == due
        await reopened_engine.dispose()

    asyncio.run(scenario())
