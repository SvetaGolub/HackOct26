import asyncio
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.db.models.enum import Currency, Periodicity
from app.db.models.payment_occurrence import PaymentOccurrence, overdue
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


class _LastPeriodSession(_Session):
    def __init__(self, period):
        super().__init__()
        self.period = period

    async def execute(self, _statement):
        return _LastPeriodResult(self.period)


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


def test_schedule_creates_first_and_next_period_with_anchor_day():
    db = _Session()

    asyncio.run(
        schedule.ensure_occurrences(
            db, _recurring_payment(Periodicity.MONTHLY), today=date(2024, 2, 1)
        )
    )

    assert [occ.due_date for occ in db.added] == [
        date(2024, 1, 31),
        date(2024, 2, 29),
    ]
    assert [occ.period for occ in db.added] == [
        date(2024, 1, 1),
        date(2024, 2, 1),
    ]


def test_schedule_creates_first_two_periods_even_when_due_date_is_far_ahead():
    db = _Session()
    recurring = _recurring_payment(Periodicity.MONTHLY)
    recurring.first_due_date = date(2028, 1, 31)

    asyncio.run(
        schedule.ensure_occurrences(db, recurring, today=date(2024, 2, 1))
    )

    assert [occ.due_date for occ in db.added] == [
        date(2028, 1, 31),
        date(2028, 2, 29),
    ]


def test_schedule_skips_missed_months_and_preserves_anchor_day():
    db = _LastPeriodSession(date(2024, 2, 1))

    asyncio.run(
        schedule.ensure_occurrences(
            db, _recurring_payment(Periodicity.MONTHLY), today=date(2024, 3, 1)
        )
    )

    assert [occ.due_date for occ in db.added] == [date(2024, 3, 31)]
    assert [occ.period for occ in db.added] == [
        date(2024, 3, 1),
    ]


class _LastPeriodResult:
    def __init__(self, period):
        self.period = period

    def scalar_one_or_none(self):
        return self.period


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


def test_occurrence_patch_does_not_allow_rescheduling():
    with pytest.raises(ValueError):
        OccurrenceUpdate(due_date=date(2024, 2, 1))


def test_payment_cancellation_clears_date_even_if_provided():
    update = OccurrenceUpdate(is_paid=False, paid_date=date(2024, 1, 1))
    assert update.is_paid is False


def test_occurrence_update_rejects_unknown_fields():
    with pytest.raises(ValueError):
        OccurrenceUpdate(is_paid=True, unknown=True)


def test_occurrence_history_is_restricted_from_cascade_delete():
    foreign_key = next(
        iter(PaymentOccurrence.__table__.c.recurring_payment_id.foreign_keys)
    )
    assert foreign_key.ondelete == "RESTRICT"


def test_occurrences_have_due_date_and_payment_status_index():
    index = next(
        index for index in PaymentOccurrence.__table__.indexes
        if index.name == "ix_occurrence_due_paid"
    )
    assert [column.name for column in index.columns] == ["due_date", "is_paid"]
