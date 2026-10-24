import asyncio
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.config import settings
from app.db.database import Base
from app.db.models import Department, User
from app.db.models.enum import UserRole
from app.db.services.auth_service import AuthService
from app.main import app


@pytest.fixture
def acceptance_db(monkeypatch):
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "test-signing-key-with-at-least-32-bytes")
    monkeypatch.setattr(settings, "ADMIN_LOGIN", "admin@example.com")
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", "AdminPass123")
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async def create_schema_and_users():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_maker() as db:
            department = Department(name="Acceptance")
            db.add(department)
            await db.flush()
            await AuthService.ensure_system_admin(db)
            db.add(
                User(
                    email="user@example.com",
                    password_hash=AuthService.get_password_hash("UserPass123"),
                    full_name="Acceptance User",
                    role=UserRole.USER,
                    department_id=department.id,
                    telegram_id=123456789,
                )
            )
            await db.commit()

    async def override_get_db():
        async with session_maker() as session:
            yield session

    asyncio.run(create_schema_and_users())
    app.dependency_overrides[get_db] = override_get_db
    try:
        yield session_maker
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())
