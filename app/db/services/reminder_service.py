import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Awaitable, Callable

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import PaymentOccurrence, RecurringPayment, ReminderLog, User
from app.db.services.schedule import ensure_occurrences, today_local

logger = logging.getLogger(__name__)

REMINDER_DAYS = getattr(settings, "REMINDER_DAYS", 3)  # ТЗ: минимум за 3 дня

SendFunc = Callable[[int | str, str, int], Awaitable[bool]]  # (chat/telegram id, text, occurrence_id) -> доставлено ли


@dataclass
class Reminder:
    occurrence_id: int
    user_id: int
    telegram_id: int
    text: str


def format_message(occ: PaymentOccurrence) -> str:
    amount = f"{occ.amount:,.2f}".replace(",", " ")
    currency = getattr(occ.currency, "value", occ.currency)
    return (
        "🔔 Напоминание об оплате\n"
        f"Название: {occ.title}\n"
        f"Сумма: {amount} {currency}\n"
        f"Дата оплаты: {occ.due_date:%d.%m.%Y}"
    )


class ReminderService:
    @staticmethod
    async def _due_occurrences(db: AsyncSession, today: date) -> list[PaymentOccurrence]:
        """Неоплаченные периоды активных платежей, до срока которых осталось не больше
        REMINDER_DAYS дней (или срок уже прошёл: платёж добавили поздно)."""
        limit_date = today + timedelta(days=REMINDER_DAYS)
        return list((await db.execute(
            select(PaymentOccurrence)
            .join(RecurringPayment, RecurringPayment.id == PaymentOccurrence.recurring_payment_id)
            .where(
                RecurringPayment.is_active.is_(True),
                PaymentOccurrence.is_paid.is_(False),
                PaymentOccurrence.due_date <= limit_date,
            )
        )).scalars().all())

    @classmethod
    async def collect(cls, db: AsyncSession, today: date | None = None) -> list[Reminder]:
        """Кому и что отправить лично: пользователям с привязанным Telegram, ещё без напоминания."""
        occs = await cls._due_occurrences(db, today or today_local())
        if not occs:
            return []

        sent = {
            (r.occurrence_id, r.user_id)
            for r in (await db.execute(
                select(ReminderLog).where(ReminderLog.occurrence_id.in_([o.id for o in occs]))
            )).scalars().all()
        }
<<<<<<< HEAD
        department_ids = {o.department_id for o in occs if o.department_id is not None}
        users_stmt = select(User).where(User.telegram_id.is_not(None))
        if department_ids and not any(o.department_id is None for o in occs):
            users_stmt = users_stmt.where(User.department_id.in_(department_ids))
        users = (await db.execute(users_stmt)).scalars().all()
=======
        users = (await db.execute(select(User).where(User.telegram_id.is_not(None)))).scalars().all()
>>>>>>> 7d3683a (пу пу пу)

        return [
            Reminder(occ.id, u.id, u.telegram_id, format_message(occ))
            for occ in occs
            for u in users
<<<<<<< HEAD
            if (occ.department_id is None or occ.department_id == u.department_id)
            and (occ.id, u.id) not in sent
=======
            if (occ.id, u.id) not in sent
>>>>>>> 7d3683a (пу пу пу)
        ]

    @classmethod
    async def collect_chat(cls, db: AsyncSession, today: date | None = None) -> list[tuple[int, str]]:
        """Периоды, о которых ещё не напоминали в общий чат: [(occurrence_id, text)]."""
        occs = await cls._due_occurrences(db, today or today_local())
        return [(o.id, format_message(o)) for o in occs if o.chat_notified_at is None]

    @staticmethod
    async def _reserve_chat(db: AsyncSession, occurrence_id: int) -> bool:
        """Атомарно помечает период как отправленный в чат; False, если кто-то уже успел."""
        res = await db.execute(
            update(PaymentOccurrence)
            .where(PaymentOccurrence.id == occurrence_id, PaymentOccurrence.chat_notified_at.is_(None))
            .values(chat_notified_at=func.now())
        )
        await db.commit()
        return res.rowcount == 1

    @staticmethod
    async def _release_chat(db: AsyncSession, occurrence_id: int) -> None:
        await db.execute(
            update(PaymentOccurrence).where(PaymentOccurrence.id == occurrence_id).values(chat_notified_at=None)
        )
        await db.commit()

    @staticmethod
    async def _reserve(db: AsyncSession, occurrence_id: int, user_id: int) -> bool:
        """Резервирует отправку: уникальный индекс гарантирует отсутствие дублей даже при гонке."""
        db.add(ReminderLog(occurrence_id=occurrence_id, user_id=user_id))
        try:
            await db.commit()
            return True
        except IntegrityError:
            await db.rollback()
            return False

    @staticmethod
    async def _release(db: AsyncSession, occurrence_id: int, user_id: int) -> None:
        await db.execute(delete(ReminderLog).where(
            ReminderLog.occurrence_id == occurrence_id, ReminderLog.user_id == user_id
        ))
        await db.commit()

    @classmethod
    async def tick(cls, db: AsyncSession, send: SendFunc, chat_id: int | str | None = None) -> int:
        """Один проход планировщика: досоздать периоды и разослать напоминания.

        Напоминания уходят в общий чат (chat_id из .env, если задан) и лично привязанным пользователям.
        Запускайте из APScheduler с max_instances=1 (раз в минуту хватит). Возвращает число отправленных.
        Если отправка не удалась, резерв снимается и напоминание уйдёт на следующем проходе.
        """
        active = (await db.execute(
            select(RecurringPayment).where(RecurringPayment.is_active.is_(True))
        )).scalars().all()
        for rp in active:
            try:
                await ensure_occurrences(db, rp)
                await db.commit()
            except IntegrityError:  # параллельная генерация: период уже создан
                await db.rollback()

        delivered = 0
        for r in await cls.collect(db):
            if not await cls._reserve(db, r.occurrence_id, r.user_id):
                continue
            try:
                ok = await send(r.telegram_id, r.text, r.occurrence_id)
            except Exception:  # noqa: BLE001
                logger.exception("Ошибка отправки напоминания user=%s occ=%s", r.user_id, r.occurrence_id)
                ok = False
            if ok:
                delivered += 1
            else:
                await cls._release(db, r.occurrence_id, r.user_id)

        if chat_id is not None:
            for occ_id, text in await cls.collect_chat(db):
                if not await cls._reserve_chat(db, occ_id):
                    continue
                try:
                    ok = await send(chat_id, text, occ_id)
                except Exception:  # noqa: BLE001
                    logger.exception("Ошибка отправки в чат occ=%s", occ_id)
                    ok = False
                if ok:
                    delivered += 1
                else:
                    await cls._release_chat(db, occ_id)
        return delivered