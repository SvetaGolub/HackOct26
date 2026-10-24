import asyncio

from sqlalchemy import select

from app.db.models import PaymentOccurrence, RecurringPayment, User
from app.db.models.enum import Currency, UserRole
from app.db.services.auth_service import AuthService
from test.seed import DEMO_PASSWORD, DEMO_USER_LOGIN, seed_demo_data


def test_demo_seed_is_idempotent_and_matches_current_application_models(acceptance_db):
    async def scenario():
        async with acceptance_db() as db:
            await AuthService.ensure_system_admin(db)
            assert await seed_demo_data(db) is True
            assert await seed_demo_data(db) is False

            demo_user = (
                await db.execute(select(User).where(User.login == DEMO_USER_LOGIN))
            ).scalar_one()
            assert demo_user.role == UserRole.USER
            assert AuthService.verify_password(DEMO_PASSWORD, demo_user.password_hash)

            payments = (await db.execute(select(RecurringPayment))).scalars().all()
            assert {payment.currency for payment in payments} == set(Currency)
            occurrences = (await db.execute(select(PaymentOccurrence))).scalars().all()
            assert any(occurrence.is_paid for occurrence in occurrences)
            assert any(not occurrence.is_paid for occurrence in occurrences)

    asyncio.run(scenario())
