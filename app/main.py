import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import uvicorn
from aiogram.exceptions import TelegramAPIError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from sqlalchemy import text

from app.admin_panel.setup import setup_admin
from app.api.v1.auth import router as auth_router
from app.api.v1.payments import router as payments_router
from app.api.v1.users import router as users_router
from app.api.v1.audit_log import router as audit_log_router
from app.api.v1.feedback import router as feedback_router
from app.api.v1.departments import router as departments_router
from app.config import settings
from app.db.services import AuthService, ReminderService
from app.db.schema_compat import ensure_schema_compat
from app.db.session import async_session_maker, engine
from app.tg_bot.keyboards import pay_keyboard
from app.tg_bot.loader import bot, dp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def wait_for_db(retries: int = 30, delay: float = 2.0) -> None:
    """MySQL в docker поднимается дольше приложения: ждём готовности."""
    for attempt in range(1, retries + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return
        except Exception:  # noqa: BLE001
            logger.info("Ждём БД (%s/%s)...", attempt, retries)
            await asyncio.sleep(delay)
    raise RuntimeError("База данных недоступна")


async def send_telegram(chat_id: int | str, text_: str, occurrence_id: int) -> bool:
    """Напоминание с кнопкой «Оплачено» (в общий чат или лично пользователю).

    False означает «не доставлено»: ReminderService.tick снимет резерв и повторит позже.
    """
    try:
        await bot.send_message(chat_id, text_, reply_markup=pay_keyboard(occurrence_id))
        return True
    except TelegramAPIError as exc:
        logger.warning("Telegram: не доставлено %s: %s", chat_id, exc)
        return False


async def run_reminders() -> None:
    """Задача планировщика. Исключения не должны убивать расписание."""
    try:
        async with async_session_maker() as db:
            await ReminderService.tick(db, send_telegram, settings.telegram_chat_id)
    except Exception:  # noqa: BLE001
        logger.exception("Сбой прохода напоминаний")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await wait_for_db()
    # На случай, если образ/alembic на сервере отстают от моделей
    await ensure_schema_compat(engine)
    async with async_session_maker() as db:
        await AuthService.ensure_system_admin(db)

    if not settings.telegram_chat_id:
        logger.warning(
            "TELEGRAM_CHAT_ID не задан: напоминания в общий чат по ТЗ отключены"
        )

    tz = ZoneInfo(settings.TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(
        run_reminders, "interval", minutes=1,
        next_run_time=datetime.now(tz),  # первая проверка сразу при старте
        max_instances=1, coalesce=True,
    )
    scheduler.start()

    # handle_signals=False: сигналы остановки обрабатывает uvicorn, а не aiogram
    bot_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))

    yield

    scheduler.shutdown(wait=False)
    bot_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await bot_task
    await bot.session.close()
    await engine.dispose()


app = FastAPI(
    title="Invoice Keeper API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url="/api/v1/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth_router, payments_router, users_router, audit_log_router, feedback_router, departments_router):
    app.include_router(r, prefix="/api/v1")


@app.get("/api/v1/docs", include_in_schema=False)
async def swagger_ui():
    return get_swagger_ui_html(openapi_url=app.openapi_url, title=app.title + " - Swagger UI")


setup_admin(app, engine)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")