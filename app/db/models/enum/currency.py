from enum import Enum


class Currency(str, Enum):
    USD = "USD"
    RUB = "RUB"
    EUR = "EUR"


# Обратная совместимость со старым именем
CURRENCY = Currency


class Periodicity(str, Enum):
    MONTHLY = "monthly"
    ONE_TIME = "one_time"  # разовый платёж: генерируется ровно один период