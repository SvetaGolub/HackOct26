import asyncio
import logging
from datetime import datetime, timedelta, timezone

import uvicorn
from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from sqladmin import Admin
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.future import select

from app.db.session import *
from app.db.models import *
from app.admin_panel.views import PaymentAdmin, UserAdmin
from app.tg_bot.loader import bot, dp

from app.api.v1.auth import router as auth_router
from app.api.v1.payments import router as payments_router
from app.api.v1.users import router as users_router

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация FastAPI приложения
app = FastAPI(
    title="Payment Control API",
    version="1.0.0",
    docs_url=None,
    redoc_url=None
)

# Подключение роутеров API с префиксом /api/v1
app.include_router(auth_router, prefix="/api/v1")
app.include_router(payments_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")


# Настройка кастомной Swagger-документации
@app.get("/api/v1/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Swagger-документация на кастомном эндпоинте согласно спецификации задания."""
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=app.title + " - Swagger UI"
    )


# Подключаем панель администратора sqladmin к FastAPI
admin = Admin(app, engine)
admin.add_view(UserAdmin)
admin.add_view(PaymentAdmin)


# ==============================================================================
# APSCHEDULER: Периодическая проверка дедлайнов (за 3 дня)
# ==============================================================================

async def check_payment_deadlines():
    """Проверка платежей, до срока оплаты которых осталось ровно 3 дня."""
    logger.info("Запуск периодической проверки дедлайнов по платежам...")

    async with async_session_maker() as session:
        now = datetime.now(timezone.utc)
        target_date_start = (now + timedelta(days=3)).replace(hour=0, minute=0, second=0, microsecond=0)
        target_date_end = target_date_start + timedelta(days=1)

        # Выбираем неоплаченные платежи, которые попадают в окно через 3 дня
        query = (
            select(Payment, User)
            .join(User, Payment.user_id == User.id)
            .where(
                Payment.status != "Оплачен",
                Payment.due_date >= target_date_start,
                Payment.due_date < target_date_end
            )
        )

        result = await session.execute(query)
        records = result.all()

        for payment, user in records:
            try:
                # Отправка уведомления ответственному сотруднику через aiogram бота
                message_text = (
                    f"⚠️ **Напоминание о платеже!**\n\n"
                    f"Уважаемый(ая) {user.full_name}, до крайнего срока оплаты платежа "
                    f"«{payment.description}» осталось 3 дня!\n"
                    f"**Сумма:** {payment.sum} {payment.currency}\n"
                    f"**Дедлайн:** {payment.due_date.strftime('%d.%m.%Y %H:%M')}"
                )
                await bot.send_message(chat_id=user.telegram_id, text=message_text, parse_mode="Markdown")
                logger.info(f"Уведомление для пользователя {user.id} по платежу {payment.id} успешно отправлено.")
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление пользователю {user.id} в Telegram: {e}")


# ==============================================================================
# АСИНХРОННЫЕ ЗАДАЧИ ДЛЯ RUNTIME
# ==============================================================================

async def run_fastapi():
    """Запуск веб-сервера Uvicorn (FastAPI API + SQLAdmin панель)."""
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def run_bot():
    """Запуск Telegram-бота в режиме Long Polling."""
    await dp.start_polling(bot)


async def run_scheduler():
    """Инициализация и запуск APScheduler."""
    scheduler = AsyncIOScheduler()

    scheduler.add_job(check_payment_deadlines, trigger='cron', hour=0, minute=0)
    scheduler.start()  # У AsyncIOScheduler метод start() синхронный, await перед ним НЕ нужен

    while True:
        await asyncio.sleep(3600)


async def main():
    """Главная точка входа для параллельного запуска сервисов."""
    await asyncio.gather(
        run_fastapi(),
        run_bot(),
        run_scheduler()
    )


if __name__ == "__main__":
    asyncio.run(main())
