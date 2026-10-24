import calendar
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import PaymentOccurrence, RecurringPayment
from app.db.models.enum import Periodicity

HORIZON_DAYS = 62  # планировщик держит впереди не более двух месяцев


def today_local() -> date:
    """Сегодня в часовом поясе из настроек (.env), а не в поясе сервера."""
    return datetime.now(ZoneInfo(settings.TIMEZONE)).date()


def clamp_date(year: int, month: int, anchor_day: int) -> date:
    """Нет такого числа в месяце: берём последний день месяца."""
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(anchor_day, last))


def add_month(period: date) -> date:
    """Первое число следующего месяца."""
    return date(period.year + (period.month == 12), period.month % 12 + 1, 1)


async def ensure_occurrences(db: AsyncSession, rp: RecurringPayment, today: date | None = None) -> None:
    """Создаёт первый и следующий периоды, затем пополняет расписание.

    Существующие периоды определяют расписание. Пропущенные месяцы не создаются
    задним числом; после старого периода генерация продолжается с текущего месяца.
    Просрочка генерацию не останавливает.
    Не коммитит: коммит делает вызывающий код. Дубли ловит uq_occurrence_period.
    """
    if not rp.is_active:
        return
    today = today or today_local()
    horizon = today + timedelta(days=HORIZON_DAYS)

    last_period = (await db.execute(
        select(func.max(PaymentOccurrence.period)).where(PaymentOccurrence.recurring_payment_id == rp.id)
    )).scalar_one_or_none()

    initial_periods = last_period is None
    first = initial_periods
    period = rp.first_due_date.replace(day=1) if initial_periods else add_month(last_period)
    if not initial_periods:
        current_period = today.replace(day=1)
        if period < current_period:
            period = current_period

    periods_to_create = 2 if first and rp.periodicity == Periodicity.MONTHLY else 1
    for _ in range(periods_to_create):
        due = clamp_date(period.year, period.month, rp.anchor_day)
        if not initial_periods and due > horizon:
            break
        db.add(PaymentOccurrence(
            recurring_payment_id=rp.id,
            title=rp.title,
            amount=rp.amount,
            currency=rp.currency,
            period=period,
            due_date=due,
        ))
        first = False
        if rp.periodicity == Periodicity.ONE_TIME:
            break
        period = add_month(period)
    await db.flush()