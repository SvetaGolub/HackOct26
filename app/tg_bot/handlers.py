# app/tg_bot/handlers.py
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.future import select

from app.db.session import async_session_maker
from app.db.models import User

router = Router()


@router.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "Привет! Я напоминаю о платежах.\n"
        "Отправьте email, под которым вы входите в панель, чтобы привязать аккаунт."
    )


@router.message(F.text.contains("@"))
async def bind_email(message: Message):
    email = message.text.strip().lower()
    async with async_session_maker() as session:
        user = (await session.execute(
            select(User).where(User.email == email)
        )).scalar_one_or_none()

        if not user:
            await message.answer("Пользователь с таким email не найден.")
            return

        user.telegram_id = message.from_user.id
        await session.commit()

    await message.answer("Готово! Напоминания будут приходить сюда.")