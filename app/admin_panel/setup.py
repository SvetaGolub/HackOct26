from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy.future import select
from starlette.requests import Request

from app.config import settings
from app.db.models import PaymentOccurrence, RecurringPayment, User
from app.db.models.enum import UserRole
from app.db.services.auth_service import AuthService
from app.db.session import async_session_maker


async def email(request: Request) -> bool:
    form = await request.form()
    async with async_session_maker() as db:
        user = (await db.execute(
            select(User).where(User.email == form.get("username"))
        )).scalar_one_or_none()
    if (user and user.role == UserRole.ADMIN.value
            and AuthService.verify_password(str(form.get("password")), user.password_hash)):
        request.session.update({"admin_id": user.id})
        return True
    return False


async def emailout(request: Request) -> bool:
    request.session.clear()
    return True


class AdminAuth(AuthenticationBackend):

    async def authenticate(self, request: Request) -> bool:
        return "admin_id" in request.session


class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.email, User.full_name, User.role, User.telegram_id]
    can_create = False   # пароль нужно хэшировать, создавайте через API
    can_edit = False


class RecurringPaymentAdmin(ModelView, model=RecurringPayment):
    column_list = [RecurringPayment.id, RecurringPayment.title, RecurringPayment.amount,
                   RecurringPayment.currency, RecurringPayment.is_active]
    can_create = False


class OccurrenceAdmin(ModelView, model=PaymentOccurrence):
    column_list = [PaymentOccurrence.id, PaymentOccurrence.title, PaymentOccurrence.amount,
                   PaymentOccurrence.currency, PaymentOccurrence.due_date,
                   PaymentOccurrence.is_paid, PaymentOccurrence.paid_date]


def setup_admin(app, engine) -> None:
    admin = Admin(app, engine, authentication_backend=AdminAuth(secret_key=settings.jwt_secret_key))
    admin.add_view(UserAdmin)
    admin.add_view(RecurringPaymentAdmin)
    admin.add_view(OccurrenceAdmin)