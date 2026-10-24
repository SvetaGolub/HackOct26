from datetime import date
from decimal import Decimal

import pytest

from app.db.models.enum import Currency
from app.db.schemas.expense_request import ExpenseRequestCreate


def test_expense_request_accepts_positive_amount_and_currency():
    request = ExpenseRequestCreate(
        title="Office supplies",
        amount=Decimal("125.50"),
        currency=Currency.RUB,
        desired_date=date(2026, 11, 1),
    )

    assert request.amount == Decimal("125.50")
    assert request.currency is Currency.RUB
    assert request.periodicity.value == "monthly"


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-1"), Decimal("1.001")])
def test_expense_request_rejects_nonpositive_or_overprecise_amount(amount):
    with pytest.raises(ValueError):
        ExpenseRequestCreate(
            title="Office supplies",
            amount=amount,
            currency=Currency.RUB,
            desired_date=date(2026, 11, 1),
        )


def test_expense_request_requires_a_title_and_desired_date():
    with pytest.raises(ValueError):
        ExpenseRequestCreate(
            title="",
            amount=Decimal("10"),
            currency=Currency.USD,
            desired_date=date(2026, 11, 1),
        )
