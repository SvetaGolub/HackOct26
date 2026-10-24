import asyncio

from sqlalchemy import select

from app.db.models import Department, PaymentOccurrence, RecurringPayment, User
from app.db.models.enum import Currency, UserRole
from test.seed import DEMO_PASSWORD, USERS, seed_demo_data
from app.db.services.auth_service import AuthService


def test_demo_seed_is_idempotent_and_matches_current_application_models(acceptance_db):
    async def scenario():
        async with acceptance_db() as db:
            await AuthService.ensure_system_admin(db)
            assert await seed_demo_data(db) is True
            assert await seed_demo_data(db) is False

            users = (await db.execute(select(User))).scalars().all()
            demo_users = [user for user in users if not user.is_system]
            seeded_users = [user for user in demo_users if user.email in {item[1] for item in USERS}]
            assert len(seeded_users) == len(USERS) == 6
            assert {user.role for user in seeded_users} == {
                UserRole.USER,
                UserRole.ACCOUNTANT,
            }
            assert all(user.department_id is not None for user in seeded_users)
            assert AuthService.verify_password(DEMO_PASSWORD, seeded_users[0].password_hash)
            assert {department.name for department in (await db.execute(select(Department))).scalars()} == {
                "Разработка",
                "Маркетинг",
                "Офис",
                "Acceptance",
            }

            payments = (await db.execute(select(RecurringPayment))).scalars().all()
            assert {payment.currency for payment in payments} == set(Currency)
            occurrences = (await db.execute(select(PaymentOccurrence))).scalars().all()
            assert any(occurrence.is_paid for occurrence in occurrences)
            assert any(not occurrence.is_paid for occurrence in occurrences)

    asyncio.run(scenario())
