# app/tg_bot/keyboards.py
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def pay_keyboard(occurrence_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Оплачено", callback_data=f"paid:{occurrence_id}")
    ]])


def undo_keyboard(occurrence_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="↩️ Отменить оплату", callback_data=f"unpaid:{occurrence_id}")
    ]])