# app/tg_bot/handlers.py
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from fastapi import HTTPException

from app.db.schemas import OccurrenceUpdate
from app.db.services import PaymentService, TelegramLinkService
from app.db.session import async_session_maker
from app.tg_bot.keyboards import pay_keyboard, undo_keyboard

router = Router()
# Только личные чаты: напоминания приходят пользователю в личку
router.message.filter(F.chat.type == "private")

HELP = (
    "Привет! Я напоминаю о платежах вашего отдела.\n\n"
    "Как привязать аккаунт:\n"
    "1. Войдите в панель и нажмите «Привязать Telegram» (получите одноразовый код).\n"
    "2. Отправьте мне: /link КОД\n\n"
    "Отвязать аккаунт: /unlink"
)


async def _link(message: Message, code: str) -> None:
    async with async_session_maker() as db:
        user = await TelegramLinkService.consume(db, code, message.from_user.id)
    if user is None:
        await message.answer("Код неверный или истёк. Получите новый код в панели.")
        return
    await message.answer(f"Готово, {user.full_name}! Напоминания о платежах будут приходить сюда.")


@router.message(CommandStart(deep_link=True))
async def start_with_code(message: Message, command: CommandObject):
    """Переход по ссылке t.me/<bot>?start=<код>."""
    await _link(message, command.args)


@router.message(CommandStart())
async def start(message: Message):
    await message.answer(HELP)


@router.message(Command("link"))
async def link(message: Message, command: CommandObject):
    if not command.args:
        await message.answer("Укажите код из панели: /link КОД")
        return
    await _link(message, command.args.strip())


@router.message(Command("unlink"))
async def unlink(message: Message):
    async with async_session_maker() as db:
        done = await TelegramLinkService.unlink_telegram(db, message.from_user.id)
    await message.answer("Аккаунт отвязан." if done else "Этот Telegram ни к какому аккаунту не привязан.")


# ---------- кнопки «Оплачено» / «Отменить оплату» в сообщении напоминания ----------

PAID_MARK = "\n\n✅ Оплачено"


def _parse_id(data: str | None) -> int | None:
    try:
        return int((data or "").split(":", 1)[1])
    except (IndexError, ValueError):
        return None


def _base_text(callback: CallbackQuery) -> str:
    """Текст напоминания без отметки об оплате."""
    text = callback.message.text if isinstance(callback.message, Message) else ""
    return (text or "").split(PAID_MARK, 1)[0]


async def _edit(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    if not isinstance(callback.message, Message):
        return
    try:
        await callback.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:  # «message is not modified» и т.п.
        pass


@router.callback_query(F.data.startswith("paid:"))
async def mark_paid(callback: CallbackQuery):
    occ_id = _parse_id(callback.data)
    if occ_id is None:
        await callback.answer("Некорректная кнопка", show_alert=True)
        return

    async with async_session_maker() as db:
        user = await TelegramLinkService.get_user_by_telegram_id(db, callback.from_user.id)
        if user is None:
            await callback.answer("Аккаунт не привязан. Получите код в панели и отправьте /link КОД",
                                  show_alert=True)
            return
        try:
            # права и границы отдела проверяет сам сервис, как и для обычного API
            data = await PaymentService.get_occurrence(db, occ_id, user)
            already = data.is_paid
            if not already:
                data = await PaymentService.update_occurrence(db, occ_id, OccurrenceUpdate(is_paid=True), user)
        except HTTPException as exc:
            await callback.answer(str(exc.detail), show_alert=True)
            return

    late = " (с опозданием)" if data.overdue else ""
    await _edit(callback, f"{_base_text(callback)}{PAID_MARK} {data.paid_date:%d.%m.%Y}{late}", undo_keyboard(occ_id))
    await callback.answer("Уже отмечено ранее" if already else "Отмечено как оплаченное")


@router.callback_query(F.data.startswith("unpaid:"))
async def mark_unpaid(callback: CallbackQuery):
    occ_id = _parse_id(callback.data)
    if occ_id is None:
        await callback.answer("Некорректная кнопка", show_alert=True)
        return

    async with async_session_maker() as db:
        user = await TelegramLinkService.get_user_by_telegram_id(db, callback.from_user.id)
        if user is None:
            await callback.answer("Аккаунт не привязан", show_alert=True)
            return
        try:
            await PaymentService.update_occurrence(db, occ_id, OccurrenceUpdate(is_paid=False), user)
        except HTTPException as exc:
            await callback.answer(str(exc.detail), show_alert=True)
            return

    await _edit(callback, _base_text(callback), pay_keyboard(occ_id))
    await callback.answer("Отметка об оплате снята")