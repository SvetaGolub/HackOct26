import asyncio
from decimal import Decimal

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db.database import Base
from app.db.models import Department, User
from app.db.models.enum import UserRole
from app.main import app
from app.config import settings
from app.db.services.auth_service import AuthService


@pytest.fixture
def test_database(monkeypatch):
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "test-signing-key-with-at-least-32-bytes")
    monkeypatch.setattr(settings, "ADMIN_LOGIN", "admin@example.com")
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", "AdminPass123")
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async def create_schema():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    asyncio.run(create_schema())
    app.dependency_overrides[get_db] = override_get_db
    try:
        yield session_maker
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())


def test_login_me_and_department_role_boundaries(test_database):
    async def scenario():
        async with test_database() as db:
            alpha = Department(name="Alpha")
            beta = Department(name="Beta")
            db.add_all([alpha, beta])
            await db.flush()

            await AuthService.ensure_system_admin(db)
            await AuthService.ensure_system_admin(db)
            employee = User(
                email="employee@example.com",
                password_hash=AuthService.get_password_hash("EmployeePass123"),
                full_name="Employee",
                role=UserRole.USER,
                department_id=alpha.id,
            )
            accountant = User(
                email="accountant@example.com",
                password_hash=AuthService.get_password_hash("AccountantPass123"),
                full_name="Accountant",
                role=UserRole.ACCOUNTANT,
                department_id=alpha.id,
            )
            outsider = User(
                email="outsider@example.com",
                password_hash=AuthService.get_password_hash("OutsiderPass123"),
                full_name="Outsider",
                role=UserRole.USER,
                department_id=beta.id,
            )
            db.add_all([employee, accountant, outsider])
            await db.commit()

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            login = await client.post(
                "/api/v1/auth/login",
                json={"email": "employee@example.com", "password": "EmployeePass123"},
            )
            assert login.status_code == 200
            token = login.json()["accessToken"]
            auth_headers = {"Authorization": f"Bearer {token}"}

            me = await client.get("/api/v1/auth/me", headers=auth_headers)
            assert me.status_code == 200
            assert me.json()["email"] == "employee@example.com"

            assert (await client.get("/api/v1/auth/me")).status_code == 401
            assert (
                await client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": "Bearer invalid-token"},
                )
            ).status_code == 401
            assert (
                await client.post(
                    "/api/v1/auth/login",
                    json={"email": "employee@example.com", "password": "wrong-password"},
                )
            ).status_code == 401

            departments = await client.get("/api/v1/departments", headers=auth_headers)
            assert departments.status_code == 200
            assert [item["name"] for item in departments.json()] == ["Alpha"]

            denied_users = await client.get("/api/v1/users", headers=auth_headers)
            assert denied_users.status_code == 403

            created_request = await client.post(
                "/api/v1/expense-requests",
                headers=auth_headers,
                json={
                    "title": "Cloud hosting",
                    "amount": str(Decimal("45.00")),
                    "currency": "USD",
                    "periodicity": "monthly",
                    "desired_date": "2026-11-01",
                },
            )
            assert created_request.status_code == 201
            request_id = created_request.json()["id"]

            denied_approval = await client.post(
                f"/api/v1/expense-requests/{request_id}/approve",
                headers=auth_headers,
                json={},
            )
            assert denied_approval.status_code == 403

            outsider_login = await client.post(
                "/api/v1/auth/login",
                json={"email": "outsider@example.com", "password": "OutsiderPass123"},
            )
            outsider_headers = {
                "Authorization": f"Bearer {outsider_login.json()['accessToken']}"
            }
            hidden_request = await client.get(
                f"/api/v1/expense-requests/{request_id}", headers=outsider_headers
            )
            assert hidden_request.status_code == 404

            accountant_login = await client.post(
                "/api/v1/auth/login",
                json={"email": "accountant@example.com", "password": "AccountantPass123"},
            )
            accountant_headers = {
                "Authorization": f"Bearer {accountant_login.json()['accessToken']}"
            }
            approval = await client.post(
                f"/api/v1/expense-requests/{request_id}/approve",
                headers=accountant_headers,
                json={},
            )
            assert approval.status_code == 200
            assert approval.json()["status"] == "approved"
            assert approval.json()["recurring_payment_id"] is not None

            other_dept_request = await client.post(
                "/api/v1/expense-requests",
                headers=outsider_headers,
                json={
                    "title": "Other department",
                    "amount": "10.00",
                    "currency": "RUB",
                    "desired_date": "2026-11-01",
                },
            )
            assert other_dept_request.status_code == 201

            admin_login = await client.post(
                "/api/v1/auth/login",
                json={"login": "admin@example.com", "password": "AdminPass123"},
            )
            assert admin_login.status_code == 200
            admin_headers = {
                "Authorization": f"Bearer {admin_login.json()['accessToken']}"
            }
            all_departments = await client.get(
                "/api/v1/departments", headers=admin_headers
            )
            assert {item["name"] for item in all_departments.json()} == {"Alpha", "Beta"}

            new_user = await client.post(
                "/api/v1/users",
                headers=admin_headers,
                json={"email": "new@example.com", "password": "NewPass123"},
            )
            assert new_user.status_code == 201
            assert new_user.json()["full_name"] == "new@example.com"
            assert new_user.json()["department_id"] is None

            global_payment = await client.post(
                "/api/v1/recurring-payments",
                headers=admin_headers,
                json={
                    "title": "Shared subscription",
                    "amount": "12.50",
                    "currency": "EUR",
                    "first_due_date": "2026-11-01",
                    "periodicity": "monthly",
                },
            )
            assert global_payment.status_code == 201
            assert global_payment.json()["department_id"] is None

            employee_payments = await client.get(
                "/api/v1/recurring-payments", headers=auth_headers
            )
            assert global_payment.json()["id"] in {
                payment["id"] for payment in employee_payments.json()
            }
            employee_occurrences = await client.get(
                "/api/v1/payment-occurrences", headers=auth_headers
            )
            global_occurrence = next(
                occurrence for occurrence in employee_occurrences.json()
                if occurrence["recurring_payment_id"] == global_payment.json()["id"]
            )
            assert "overdue" in global_occurrence
            occurrence_url = (
                f"/api/v1/payment-occurrences/{global_occurrence['id']}"
            )
            mark_paid = await client.patch(
                occurrence_url, headers=auth_headers, json={"is_paid": True}
            )
            assert mark_paid.status_code == 200
            assert mark_paid.json()["paid_date"] is not None

            unmark_paid = await client.patch(
                occurrence_url,
                headers=auth_headers,
                json={"is_paid": False, "paid_date": "2026-10-01"},
            )
            assert unmark_paid.status_code == 200
            assert unmark_paid.json()["paid_date"] is None

            future_payment = await client.patch(
                occurrence_url,
                headers=auth_headers,
                json={"is_paid": True, "paid_date": "2099-01-01"},
            )
            assert future_payment.status_code == 422
            reschedule = await client.patch(
                occurrence_url,
                headers=auth_headers,
                json={"due_date": "2026-12-01"},
            )
            assert reschedule.status_code == 422

            logout = await client.post("/api/v1/auth/logout", headers=auth_headers)
            assert logout.status_code == 200
            assert (
                await client.get("/api/v1/auth/me", headers=auth_headers)
            ).status_code == 401

    asyncio.run(scenario())
