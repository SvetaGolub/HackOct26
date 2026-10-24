import calendar
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import PaymentOccurrence, RecurringPayment
from app.db.models.enum import Periodicity

HORIZON_DAYS = 62  # на сколько вперёд держим созданные периоды


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
    """Досоздаёт периоды до горизонта.

    Идёт по неизменяемому period, а не по due_date, поэтому перенос срока
    бухгалтером не сдвигает и не ломает цепочку. Просрочка генерацию не останавливает.
    Не коммитит: коммит делает вызывающий код. Дубли ловит uq_occurrence_period.
    """
    if not rp.is_active:
        return
    today = today or today_local()
    horizon = today + timedelta(days=HORIZON_DAYS)

    last_period = (await db.execute(
        select(func.max(PaymentOccurrence.period)).where(PaymentOccurrence.recurring_payment_id == rp.id)
    )).scalar_one_or_none()

    first = last_period is None
    period = rp.first_due_date.replace(day=1) if first else add_month(last_period)

    while True:
        due = clamp_date(period.year, period.month, rp.anchor_day)
        if due > horizon and not first:  # первый период создаём всегда
            break
        db.add(PaymentOccurrence(
            recurring_payment_id=rp.id,
            department_id=rp.department_id,
            title=rp.title,
            amount=rp.amount,
            currency=rp.currency,
            period=period,
            original_due_date=due,
            due_date=due,
        ))
        first = False
        if rp.periodicity == Periodicity.ONE_TIME:
            break
        period = add_month(period)
    await db.flush()
