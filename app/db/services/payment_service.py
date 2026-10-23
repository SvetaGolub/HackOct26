from typing import List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException

from app.db.models import Payment, User
from app.db.schemas import *
from app.db.services.auth_servic import AuthService  # Для логирования


class PaymentService:
    @classmethod
    async def create_payment(cls, db: AsyncSession, payment_in: PaymentCreate, current_user: User) -> Payment:
        """Создание нового платежа (Только Администратор)."""
        if current_user.role != "administrator":
            await AuthService.log_access(db, current_user.id, "Попытка несанкционированного создания платежа")
            raise HTTPException(status_code=403, detail="Только администратор может добавляровать платежи")

        new_payment = Payment(
            user_id=payment_in.user_id,
            description=payment_in.description,
            status=payment_in.status,
            sum=payment_in.sum,
            currency=payment_in.currency.value,
            due_date=payment_in.due_date
        )
        db.add(new_payment)
        await db.commit()
        await db.refresh(new_payment)

        await AuthService.log_access(db, current_user.id,
                                     f"Создан платеж ID {new_payment.id} для пользователя {payment_in.user_id}")
        return new_payment

    @classmethod
    async def get_all_payments(cls, db: AsyncSession, current_user: User) -> List[Payment]:
        """Получение общего списка платежей (Доступно всем авторизованным пользователям)."""
        query = select(Payment).order_by(Payment.due_date.asc())
        result = await db.execute(query)
        payments = result.scalars().all()

        await AuthService.log_access(db, current_user.id, "Запрошен общий список платежей")
        return list(payments)

    @classmethod
    async def update_payment_status(
            cls, db: AsyncSession, payment_id: int, update_data: PaymentUpdateStatus, current_user: User
    ) -> Any | None:
        """Обновление статуса платежа и даты фактической оплаты (Может обычный Пользователь)."""
        query = select(Payment).where(Payment.id == payment_id)
        result = await db.execute(query)
        payment = result.scalar_one_or_none()

        if not payment:
            raise HTTPException(status_code=404, detail="Платеж не найден")

        # Проверка прав: Пользователь может менять статус своих платежей, либо Админ может менять любые
        if current_user.role != "administrator" and payment.user_id != current_user.id:
            await AuthService.log_access(db, current_user.id, f"Попытка изменить чужой платеж ID {payment_id}")
            raise HTTPException(status_code=403, detail="Вы можете изменять статус только своих платежей")

        # Применяем изменения
        payment.status = update_data.status
        payment.paid_at = update_data.paid_at

        await db.commit()
        await db.refresh(payment)

        await AuthService.log_access(
            db, current_user.id, f"Изменен статус платежа ID {payment_id} на '{update_data.status}'"
        )
        return payment

    @classmethod
    async def delete_payment(cls, db: AsyncSession, payment_id: int, current_user: User) -> bool:
        """Удаление платежа (Только Администратор)."""
        if current_user.role != "administrator":
            await AuthService.log_access(db, current_user.id,
                                         f"Попытка несанкционированного удаления платежа ID {payment_id}")
            raise HTTPException(status_code=403, detail="Только администратор может удалять платежи")

        query = select(Payment).where(Payment.id == payment_id)
        result = await db.execute(query)
        payment = result.scalar_one_or_none()

        if not payment:
            raise HTTPException(status_code=404, detail="Платеж не найден")

        await db.delete(payment)
        await db.commit()

        await AuthService.log_access(db, current_user.id, f"Удален платеж ID {payment_id}")
        return True