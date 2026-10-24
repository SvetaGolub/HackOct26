import asyncio
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.db.models.enum import Currency, Periodicity
from app.db.models.payment_occurrence import overdue
from app.db.schemas.payments import OccurrenceUpdate
from app.db.services import schedule


@pytest.mark.parametrize(
    ("year", "month", "anchor_day", "expected"),
    [
        (2024, 2, 31, date(2024, 2, 29)),
        (2023, 2, 31, date(2023, 2, 28)),
        (2024, 3, 31, date(2024, 3, 31)),
    ],
)
def test_monthly_due_date_clamps_to_month_end(year, month, anchor_day, expected):
    assert schedule.clamp_date(year, month, anchor_day) == expected


def test_add_month_rolls_over_year():
    assert schedule.add_month(date(2024, 12, 1)) == date(2025, 1, 1)


class _Result:
    def scalar_one_or_none(self):
        return None


class _Session:
    def __init__(self):
        self.added = []

    async def execute(self, _statement):
        return _Result()

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        pass


def _recurring_payment(periodicity):
    return SimpleNamespace(
        id=1,
        is_active=True,
        first_due_date=date(2024, 1, 31),
        anchor_day=31,
        department_id=1,
        title="Server",
        amount=Decimal("45.00"),
        currency=Currency.USD,
        periodicity=periodicity,
    )


def test_schedule_keeps_anchor_day_after_february():
    db = _Session()

    asyncio.run(
        schedule.ensure_occurrences(
            db, _recurring_payment(Periodicity.MONTHLY), today=date(2024, 2, 1)
        )
    )

    assert [occ.due_date for occ in db.added] == [
        date(2024, 1, 31),
        date(2024, 2, 29),
        date(2024, 3, 31),
    ]
    assert [occ.period for occ in db.added] == [
        date(2024, 1, 1),
        date(2024, 2, 1),
        date(2024, 3, 1),
    ]


def test_one_time_payment_creates_only_one_occurrence():
    db = _Session()

    asyncio.run(
        schedule.ensure_occurrences(
            db, _recurring_payment(Periodicity.ONE_TIME), today=date(2024, 2, 1)
        )
    )

    assert len(db.added) == 1


@pytest.mark.parametrize(
    ("due", "is_paid", "paid_date", "today", "expected"),
    [
        (date(2024, 1, 10), False, None, date(2024, 1, 10), False),
        (date(2024, 1, 10), False, None, date(2024, 1, 11), True),
        (date(2024, 1, 10), True, date(2024, 1, 10), date(2024, 1, 20), False),
        (date(2024, 1, 10), True, date(2024, 1, 11), date(2024, 1, 11), True),
    ],
)
def test_overdue_is_based_on_due_and_actual_payment_dates(
    due, is_paid, paid_date, today, expected
):
    assert overdue(due, is_paid, paid_date, today) is expected


def test_occurrence_update_requires_a_change():
    with pytest.raises(ValueError):
        OccurrenceUpdate()


def test_rescheduling_requires_a_reason():
    with pytest.raises(ValueError):
        OccurrenceUpdate(due_date=date(2024, 2, 1))

    update = OccurrenceUpdate(
        due_date=date(2024, 2, 1), reschedule_reason="Invoice delayed"
    )
    assert update.due_date == date(2024, 2, 1)


def test_payment_cancellation_cannot_include_paid_date():
    with pytest.raises(ValueError):
        OccurrenceUpdate(is_paid=False, paid_date=date(2024, 1, 1))


def test_occurrence_update_rejects_unknown_fields():
    with pytest.raises(ValueError):
        OccurrenceUpdate(is_paid=True, unknown=True)
