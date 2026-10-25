import asyncio
from datetime import timedelta
from decimal import Decimal

import httpx
from sqlalchemy import select

from app.db.models import Department, PaymentOccurrence, RecurringPayment
from app.db.models.enum import Currency, Periodicity
from app.db.services.reminder_service import ReminderService
from app.db.services.schedule import today_local
from app.main import app


async def _headers(client, login, password):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": login, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_protected_data_and_private_api_documentation(acceptance_db):
    async def scenario():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            panel = await client.get("/admin/", follow_redirects=False)
            assert panel.status_code in {302, 303}
            assert "/admin/login" in panel.headers["location"]

            for path in (
                "/api/v1/auth/me",
                "/api/v1/recurring-payments",
                "/api/v1/payment-occurrences",
                "/api/v1/payments/summary",
                "/api/v1/users",
            ):
                assert (await client.get(path)).status_code == 401

            docs = await client.get("/api/v1/docs")
            spec_response = await client.get("/api/v1/openapi.json")
            assert docs.status_code == 404
            assert spec_response.status_code == 404

    asyncio.run(scenario())


def test_roles_payment_status_deletion_and_history(acceptance_db):
    async def scenario():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            admin_headers = await _headers(client, "admin@example.com", "AdminPass123")
            user_headers = await _headers(client, "user@example.com", "UserPass123")
            today = today_local()
            due = today - timedelta(days=4)

            payload = {
                "title": "Monthly server",
                "amount": "42.50",
                "currency": "USD",
                "first_due_date": due.isoformat(),
                "periodicity": "monthly",
            }
            assert (
                await client.post("/api/v1/recurring-payments", headers=user_headers, json=payload)
            ).status_code == 403
            assert (await client.get("/api/v1/users", headers=user_headers)).status_code == 403
            assert (
                await client.post(
                    "/api/v1/users",
                    headers=user_headers,
                    json={"email": "new@example.com", "password": "NewPass123"},
                )
            ).status_code == 403

            created = await client.post(
                "/api/v1/recurring-payments", headers=admin_headers, json=payload
            )
            assert created.status_code == 201
            recurring_id = created.json()["id"]
            managed_user = await client.post(
                "/api/v1/users",
                headers=admin_headers,
                json={
                    "email": "managed@example.com",
                    "password": "ManagedPass123",
                    "full_name": "Managed User",
                },
            )
            assert managed_user.status_code == 201
            updated_user = await client.patch(
                f"/api/v1/users/{managed_user.json()['id']}",
                headers=admin_headers,
                json={"full_name": "Updated User"},
            )
            assert updated_user.status_code == 200
            assert updated_user.json()["full_name"] == "Updated User"
            assert (
                await client.delete(
                    f"/api/v1/users/{managed_user.json()['id']}", headers=admin_headers
                )
            ).status_code == 204

            occurrences = await client.get(
                "/api/v1/payment-occurrences", headers=user_headers
            )
            assert occurrences.status_code == 200
            assert len(occurrences.json()) >= 2
            assert len({item["period"] for item in occurrences.json()}) >= 2
            occurrence = min(occurrences.json(), key=lambda item: item["due_date"])
            assert {
                "amount", "currency", "due_date", "status", "paid_date", "overdue"
            } <= occurrence.keys()
            occurrence_url = f"/api/v1/payment-occurrences/{occurrence['id']}"

            marked = await client.patch(
                occurrence_url,
                headers=user_headers,
                json={"is_paid": True, "paid_date": today.isoformat()},
            )
            assert marked.status_code == 200
            assert marked.json()["overdue"] is True
            second_period = next(
                item for item in occurrences.json() if item["id"] != occurrence["id"]
            )
            other_period = await client.get(
                f"/api/v1/payment-occurrences/{second_period['id']}",
                headers=user_headers,
            )
            assert other_period.status_code == 200
            assert other_period.json()["is_paid"] is False

            corrected = await client.patch(
                occurrence_url,
                headers=user_headers,
                json={"is_paid": True, "paid_date": occurrence["due_date"]},
            )
            assert corrected.status_code == 200
            assert corrected.json()["overdue"] is False

            cancelled = await client.patch(
                occurrence_url,
                headers=user_headers,
                json={"is_paid": False, "paid_date": today.isoformat()},
            )
            assert cancelled.status_code == 200
            assert cancelled.json()["paid_date"] is None
            assert cancelled.json()["status"] == "unpaid"

            marked_again = await client.patch(
                occurrence_url,
                headers=user_headers,
                json={"is_paid": True, "paid_date": occurrence["due_date"]},
            )
            assert marked_again.status_code == 200

            assert (
                await client.delete(
                    f"/api/v1/recurring-payments/{recurring_id}", headers=user_headers
                )
            ).status_code == 403
            deleted = await client.delete(
                f"/api/v1/recurring-payments/{recurring_id}", headers=admin_headers
            )
            assert deleted.status_code == 204

            async with acceptance_db() as db:
                history = (
                    await db.execute(
                        select(PaymentOccurrence).where(
                            PaymentOccurrence.recurring_payment_id == recurring_id
                        )
                    )
                ).scalars().all()
                payment = await db.get(RecurringPayment, recurring_id)
                assert await ReminderService.collect(db, today) == []
            assert payment.is_active is False
            assert len(history) == 1
            assert history[0].is_paid is True

            system_admin_id = int(
                (
                    await client.post(
                        "/api/v1/auth/login",
                        json={"email": "admin@example.com", "password": "AdminPass123"},
                    )
                ).json()["user"]["id"]
            )
            assert (
                await client.patch(
                    f"/api/v1/users/{system_admin_id}",
                    headers=admin_headers,
                    json={"full_name": "Changed"},
                )
            ).status_code == 403
            assert (
                await client.delete(
                    f"/api/v1/users/{system_admin_id}", headers=admin_headers
                )
            ).status_code == 403

    asyncio.run(scenario())


def test_currency_summary_is_separate_and_complete(acceptance_db):
    async def scenario():
        today = today_local()
        async with acceptance_db() as db:
            department = (
                await db.execute(select(Department).where(Department.name == "Acceptance"))
            ).scalar_one()
            fixtures = [
                (Currency.RUB, "100.00", True, today, today),
                (Currency.RUB, "10.00", False, None, today),
                (Currency.USD, "20.00", True, today, today - timedelta(days=1)),
                (Currency.USD, "30.00", False, None, today - timedelta(days=1)),
                (Currency.EUR, "40.00", True, today, today),
                (Currency.EUR, "50.00", False, None, today + timedelta(days=4)),
            ]
            for index, (currency, amount, is_paid, paid_date, due_date) in enumerate(fixtures):
                recurring = RecurringPayment(
                    title=f"Summary {index}",
                    amount=Decimal(amount),
                    currency=currency,
                    periodicity=Periodicity.ONE_TIME,
                    first_due_date=due_date,
                    anchor_day=due_date.day,
                    department_id=department.id,
                )
                db.add(recurring)
                await db.flush()
                db.add(
                    PaymentOccurrence(
                        recurring_payment_id=recurring.id,
                        department_id=department.id,
                        title=recurring.title,
                        amount=recurring.amount,
                        currency=currency,
                        period=due_date.replace(day=1),
                        due_date=due_date,
                        is_paid=is_paid,
                        paid_date=paid_date,
                    )
                )
            await db.commit()

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _headers(client, "user@example.com", "UserPass123")
            response = await client.get("/api/v1/payments/summary", headers=headers)
        assert response.status_code == 200
        summaries = {row["currency"]: row for row in response.json()}
        assert set(summaries) == {"RUB", "USD", "EUR"}
        assert summaries["RUB"]["paid"] == "100.00"
        assert summaries["RUB"]["unpaid"] == "10.00"
        assert summaries["RUB"]["overdue"] == "0.00"
        assert summaries["USD"]["paid"] == "20.00"
        assert summaries["USD"]["unpaid"] == "30.00"
        assert summaries["USD"]["overdue"] == "30.00"
        assert summaries["EUR"]["paid"] == "40.00"
        assert summaries["EUR"]["unpaid"] == "50.00"
        assert summaries["EUR"]["overdue"] == "0.00"

    asyncio.run(scenario())
