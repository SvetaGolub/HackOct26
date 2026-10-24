import asyncio
import logging

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html

from app.admin_panel.setup import setup_admin
from app.api.v1.auth import router as auth_router
from app.api.v1.payments import router as payments_router
from app.api.v1.users import router as users_router
from app.config import settings
from app.db.services.bootstrap import ensure_admin
from app.db.services.reminders import check_payment_deadlines
from app.db.session import async_session_maker, engine
from app.tg_bot.loader import bot, dp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Invoice Keeper API", version="1.0.0", docs_url=None, redoc_url=None)

for r in (auth_router, payments_router, users_router):
    app.include_router(r, prefix="/api/v1")


@app.get("/api/v1/docs", include_in_schema=False)
async def swagger_ui():
    return get_swagger_ui_html(openapi_url="/openapi.json", title=app.title + " - Swagger UI")


setup_admin(app, engine)


async def run_fastapi():
    server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info"))
    await server.serve()


async def run_bot():
    await dp.start_polling(bot)


async def run_scheduler():
    scheduler = AsyncIOScheduler(timezone=settings.TIMEZONE)
    scheduler.add_job(check_payment_deadlines, "interval", minutes=10, next_run_time=None)
    scheduler.start()
    await check_payment_deadlines()          # первая проверка сразу при старте
    while True:
        await asyncio.sleep(3600)


async def main():
    await ensure_admin(async_session_maker)
    await asyncio.gather(run_fastapi(), run_bot(), run_scheduler())


if __name__ == "__main__":
    asyncio.run(main())