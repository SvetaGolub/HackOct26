# app/tg_bot/loader.py
from aiogram import Bot, Dispatcher

from app.config import settings
from app.tg_bot.handlers import router

bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
dp.include_router(router)