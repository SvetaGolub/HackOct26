from sqladmin import ModelView
from wtforms import PasswordField

from app.db.models import User, Payment, AccessLog


class UserAdmin(ModelView, model=User):
    """Отображение и управление пользователями в админ-панели."""

    name = "Пользователь"
    name_plural = "Пользователи"
    icon = "fa-solid fa-user"

    # Колонки, отображаемые в общем списке
    column_list = [
        User.id,
        User.full_name,
        User.email,
        User.role,
        User.department,
        User.telegram_id
    ]

    # Поля, по которым доступен текстовый поиск
    column_searchable_list = [User.full_name, User.email, User.department]

    # Фильтры в правой панели страницы списка
    column_filters = [User.role, User.department]

    # Поля, которые нельзя редактировать/добавлять напрямую в этих полях (пароль скрываем отдельно)
    column_details_exclude_list = [User.password_hash]

    # Кастомизация формы: заменяем стандартное текстовое поле ввода хэша пароля на скрытое поле для ввода нового пароля
    form_extra_fields = {
        "password_hash": PasswordField("Новый пароль (будет сохранен как хэш)")
    }

    # Интеграция хэширования, если администратор меняет/создает пользователя через sqladmin напрямую
    async def on_model_change(self, data: dict, model: User, is_created: bool) -> None:
        from app.db.services.auth_servic import AuthService
        if "password_hash" in data and data["password_hash"]:
            # Если поле пароля заполнено, хэшируем его перед записью в БД
            data["password_hash"] = AuthService.get_password_hash(data["password_hash"])
        elif not is_created:
            # При редактировании, если пароль пустой — не перезаписываем старый хэш
            data.pop("password_hash", None)


class PaymentAdmin(ModelView, model=Payment):
    """Отображение и управление регулярными платежами."""

    name = "Платеж"
    name_plural = "Платежи"
    icon = "fa-solid fa-credit-card"

    # Колонки для отображения в таблице платежей
    column_list = [
        Payment.id,
        Payment.user,  # Автоматически отобразит связанного пользователя через __repr__
        Payment.description,
        Payment.sum,
        Payment.currency,
        Payment.status,
        Payment.due_date,
        Payment.paid_at
    ]

    # Поля, доступные для текстового поиска
    column_searchable_list = [Payment.description, Payment.status]

    # Быстрые фильтры
    column_filters = [Payment.status, Payment.currency, Payment.due_date]

    # Сортировка по умолчанию (сначала самые срочные дедлайны)
    column_default_sort = [(Payment.due_date, False)]

    # Форматирование вывода полей (например, красивое отображение сумм)
    column_formatters = {
        Payment.sum: lambda model, attribute: f"{model.sum:,.2f}"
    }


class AccessLogAdmin(ModelView, model=AccessLog):
    """Просмотр логов безопасности системы (Только для чтения)."""

    name = "Лог безопасности"
    name_plural = "Логи безопасности"
    icon = "fa-solid fa-shield-halved"

    # Логи можно только смотреть и удалять (опционально), создавать вручную запрещено
    can_create = False
    can_edit = False

    column_list = [
        AccessLog.id,
        AccessLog.user_id,
        AccessLog.timestamp,
        AccessLog.result
    ]

    column_filters = [AccessLog.timestamp]
    column_searchable_list = [AccessLog.result]
    column_default_sort = [(AccessLog.timestamp, True)]
