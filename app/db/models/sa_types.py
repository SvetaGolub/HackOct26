from enum import Enum

from sqlalchemy import Enum as SAEnum


def str_enum(enum_cls: type[Enum], length: int = 20) -> SAEnum:
    """Enum, хранящийся в БД как VARCHAR со значениями (.value), а не именами.

    native_enum=False: без MySQL ENUM, миграции проще.
    validate_strings=True: строка вне набора значений вызывает ошибку.
    """
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )
