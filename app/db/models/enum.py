from enum import Enum


class Currency(str, Enum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


class Periodicity(str, Enum):
    MONTHLY = "monthly"      # обязательная часть ТЗ
    ONE_TIME = "one_time"    # доп. возможность: ровно один период


class UserRole(str, Enum):
    ADMIN = "admin"   # главный бухгалтер, задаётся через .env
    USER = "user"     # бухгалтер: смотрит платежи, отмечает оплату