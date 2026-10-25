import calendar
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
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
    """Первое число следующего месяца для совместимости с месячными расписаниями."""
    return date(period.year + (period.month == 12), period.month % 12 + 1, 1)


def _next_due(rp: RecurringPayment, due: date) -> date:
    if rp.periodicity == Periodicity.MONTHLY:
        next_month = add_month(due)
        return clamp_date(next_month.year, next_month.month, rp.anchor_day)
    if rp.periodicity == Periodicity.YEARLY:
        return clamp_date(due.year + 1, rp.first_due_date.month, rp.anchor_day)
    if rp.periodicity == Periodicity.WEEKLY:
        return due + timedelta(days=7)
    if rp.periodicity == Periodicity.DAILY:
        return due + timedelta(days=1)
    if rp.periodicity == Periodicity.CUSTOM:
        if not rp.interval_days:
            raise ValueError("Для пользовательской периодичности не задан интервал")
        return due + timedelta(days=rp.interval_days)
    return due


def _period_key(rp: RecurringPayment, due: date) -> date:
    return due.replace(day=1) if rp.periodicity == Periodicity.MONTHLY else due


async def ensure_occurrences(
    db: AsyncSession,
    rp: RecurringPayment,
    today: date | None = None,
    start_due_date: date | None = None,
) -> None:
    """Создаёт будущие периоды расписания в пределах горизонта планирования.

    Неоплаченные периоды не создаются задним числом. Старые месячные периоды
    сохраняют прежний ключ (первое число месяца); другие периодичности используют
    дату платежа как ключ периода.
    """
    if not rp.is_active:
        return
    today = today or today_local()
    horizon = today + timedelta(days=HORIZON_DAYS)

    if start_due_date is not None:
        due = start_due_date
        initial_monthly = rp.periodicity == Periodicity.MONTHLY
    else:
        last_due = (await db.execute(
            select(PaymentOccurrence.due_date)
            .where(PaymentOccurrence.recurring_payment_id == rp.id)
            .order_by(PaymentOccurrence.due_date.desc(), PaymentOccurrence.id.desc())
            .limit(1)
        )).scalar_one_or_none()
        initial_monthly = last_due is None and rp.periodicity == Periodicity.MONTHLY
        due = rp.first_due_date if last_due is None else _next_due(rp, last_due)

    while due < today and rp.periodicity not in {Periodicity.ONE_TIME, Periodicity.MONTHLY if initial_monthly else Periodicity.ONE_TIME}:
        due = _next_due(rp, due)

    existing_periods = set((await db.execute(
        select(PaymentOccurrence.period).where(PaymentOccurrence.recurring_payment_id == rp.id)
    )).scalars().all())
    created = 0
    while created == 0 or due <= horizon or (initial_monthly and created < 2):
        period = _period_key(rp, due)
        if period not in existing_periods:
            db.add(PaymentOccurrence(
                recurring_payment_id=rp.id,
                title=rp.title,
                amount=rp.amount,
                currency=rp.currency,
                department=rp.department,
                employee=rp.employee,
                period=period,
                due_date=due,
            ))
            existing_periods.add(period)
            created += 1
        if rp.periodicity == Periodicity.ONE_TIME:
            break
        due = _next_due(rp, due)
    await db.flush()