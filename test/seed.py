"""Тестовые данные для демо и проверки жюри.

Запуск вручную:  python -m app.db.services.seed
Автоматически:   SEED_DEMO_DATA=true в .env (выполняется при старте приложения).
Повторный запуск безопасен: если данные уже созданы, ничего не дублируется.

Все данные создаются через сервисы, поэтому заполнены история изменений (AuditLog),
периоды оплаты и права доступа работают так же, как в обычной работе.
"""
import asyncio
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Department, PaymentOccurrence, User
from app.db.models.enum import Currency, UserRole
from app.db.schemas import (
    ExpenseRequestApprove, ExpenseRequestCreate, ExpenseRequestReject, OccurrenceUpdate,
)
from app.db.services.auth_service import AuthService
from app.db.services.expense_service import ExpenseService
from app.db.services.payment_service import PaymentService
from app.db.services.schedule import today_local

DEMO_PASSWORD = "Demo12345"

DEPARTMENTS = ["Разработка", "Маркетинг", "Офис"]

# (ключ, email, ФИО, роль, отдел)
USERS = [
    ("dev_user", "dev.user@example.com", "Иван Петров", UserRole.USER, "Разработка"),
    ("dev_acc", "dev.accountant@example.com", "Мария Соколова", UserRole.ACCOUNTANT, "Разработка"),
    ("mkt_user", "mkt.user@example.com", "Анна Волкова", UserRole.USER, "Маркетинг"),
    ("mkt_acc", "mkt.accountant@example.com", "Олег Новиков", UserRole.ACCOUNTANT, "Маркетинг"),
    ("off_user", "office.user@example.com", "Дмитрий Орлов", UserRole.USER, "Офис"),
    ("off_acc", "office.accountant@example.com", "Елена Белова", UserRole.ACCOUNTANT, "Офис"),
]


async def _request(db: AsyncSession, author: User, reviewer: User | None, *, title: str, amount: str,
                   currency: Currency, due, reject_reason: str | None = None):
    """Заявка от сотрудника; затем одобрение, отказ или оставляем на рассмотрении (reviewer=None)."""
    req = await ExpenseService.create(
        db,
        ExpenseRequestCreate(title=title, amount=Decimal(amount), currency=currency, desired_date=due),
        author,
    )
    if reviewer is None:
        return req
    if reject_reason:
        return await ExpenseService.reject(db, req.id, ExpenseRequestReject(reason=reject_reason), reviewer)
    return await ExpenseService.approve(db, req.id, ExpenseRequestApprove(first_due_date=due), reviewer)


async def seed_demo_data(db: AsyncSession) -> bool:
    """Создаёт тестовые данные. False, если они уже были созданы."""
    if (await db.execute(select(User.id).where(User.email == USERS[0][1]))).first():
        return False
    admin = (await db.execute(select(User).where(User.is_system.is_(True)))).scalar_one_or_none()
    if admin is None:
        raise RuntimeError("Сначала должен быть создан администратор (AuthService.ensure_system_admin)")

    # --- отделы и пользователи ---
    depts: dict[str, Department] = {}
    for name in DEPARTMENTS:
        dept = (await db.execute(select(Department).where(Department.name == name))).scalar_one_or_none()
        if dept is None:
            dept = Department(name=name)
            db.add(dept)
        depts[name] = dept
    await db.flush()

    password_hash = AuthService.get_password_hash(DEMO_PASSWORD)
    users: dict[str, User] = {}
    for key, email, full_name, role, dept_name in USERS:
        users[key] = User(
            email=email, password_hash=password_hash, full_name=full_name,
            role=role, department_id=depts[dept_name].id,
        )
        db.add(users[key])
    await db.commit()

    today = today_local()
    day = lambda n: today + timedelta(days=n)  # noqa: E731

    # --- Разработка: сервер в USD, подписка в EUR, заявка на рассмотрении, отказ ---
    await _request(db, users["dev_user"], users["dev_acc"], title="Сервер (VPS)", amount="45.00",
                   currency=Currency.USD, due=day(2))            # напоминание придёт почти сразу
    await _request(db, users["dev_user"], users["dev_acc"], title="Подписка JetBrains", amount="24.90",
                   currency=Currency.EUR, due=day(12))
    await _request(db, users["dev_user"], None, title="Лицензия Figma", amount="15.00",
                   currency=Currency.USD, due=day(20))           # ждёт решения бухгалтера
    await _request(db, users["dev_user"], users["dev_acc"], title="Игровая консоль", amount="500.00",
                   currency=Currency.USD, due=day(7), reject_reason="Не относится к рабочим расходам")

    # --- Маркетинг: реклама, просроченный платёж, заявка на рассмотрении ---
    await _request(db, users["mkt_user"], users["mkt_acc"], title="Реклама (Яндекс Директ)", amount="50000.00",
                   currency=Currency.RUB, due=day(7))
    await _request(db, users["mkt_user"], users["mkt_acc"], title="Домен и хостинг лендинга", amount="1200.00",
                   currency=Currency.RUB, due=day(-5))           # просрочен: для показа просрочки
    await _request(db, users["mkt_user"], None, title="Услуги дизайнера", amount="30000.00",
                   currency=Currency.RUB, due=day(14))

    # --- Офис: аренда в RUB и оплаченный вовремя платёж ---
    await _request(db, users["off_user"], users["off_acc"], title="Аренда офиса", amount="120000.00",
                   currency=Currency.RUB, due=day(5))
    internet = await _request(db, users["off_user"], users["off_acc"], title="Интернет", amount="1500.00",
                              currency=Currency.RUB, due=day(-3))
    first_occ = (await db.execute(
        select(PaymentOccurrence)
        .where(PaymentOccurrence.recurring_payment_id == internet.recurring_payment_id)
        .order_by(PaymentOccurrence.due_date).limit(1)
    )).scalar_one()
    await PaymentService.update_occurrence(
        db, first_occ.id, OccurrenceUpdate(is_paid=True, paid_date=day(-4)), users["off_user"]
    )
    return True


async def _main() -> None:
    from app.db.session import async_session_maker  # импорт здесь: модуль можно подключать без БД

    async with async_session_maker() as db:
        await AuthService.ensure_system_admin(db)
        created = await seed_demo_data(db)

    if not created:
        print("Тестовые данные уже созданы, ничего не изменено.")
        return
    print("Тестовые данные созданы. Пароль всех демо-пользователей:", DEMO_PASSWORD)
    for _, email, full_name, role, dept in USERS:
        print(f"  {role.value:<11} {email:<30} {dept:<11} {full_name}")


if __name__ == "__main__":
    asyncio.run(_main())
