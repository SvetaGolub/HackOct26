# Models package.
# Импортируйте здесь ВСЕ модели, иначе Alembic не увидит их в Base.metadata.

from app.db.models.department import Department
from app.db.models.user import User
from app.db.models.expense_request import ExpenseRequest
from app.db.models.recurring_payment import RecurringPayment
from app.db.models.payment_occurrence import PaymentOccurrence
from app.db.models.reminder_log import ReminderLog
from app.db.models.audit_log import AuditLog
from app.db.models.telegram_link_code import TelegramLinkCode
from app.db.models.auth_session import AuthSession

__all__ = [
    "Department",
    "User",
    "ExpenseRequest",
    "RecurringPayment",
    "PaymentOccurrence",
    "ReminderLog",
    "AuditLog",
    "TelegramLinkCode",
    "AuthSession",
]