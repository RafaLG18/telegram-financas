"""Inline keyboards.

Telegram's callback_data has a hard 64-byte limit, so it carries only short
pointers ("action:draft:value"). The real data lives in the database.

Button labels are read by the user, so they stay in pt-BR.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .models import Category, EXPENSE, INCOME

CB_KIND = "kind"
CB_CATEGORY = "cat"
CB_DATE = "date"
CB_CONFIRM = "ok"
CB_CANCEL = "no"
CB_CHANGE_DATE = "dt?"
CB_FREE_DATE = "dtf"
CB_UNDO = "undo"


def kind_keyboard(draft_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔴 Gasto", callback_data=f"{CB_KIND}:{draft_id}:{EXPENSE}")
    b.button(text="🟢 Entrada", callback_data=f"{CB_KIND}:{draft_id}:{INCOME}")
    b.button(text="✖️ Cancelar", callback_data=f"{CB_CANCEL}:{draft_id}")
    b.adjust(2, 1)
    return b.as_markup()


def categories_keyboard(
    draft_id: str, categories: list[Category]
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for cat in categories:
        b.button(text=cat.name, callback_data=f"{CB_CATEGORY}:{draft_id}:{cat.id}")
    b.button(text="✖️ Cancelar", callback_data=f"{CB_CANCEL}:{draft_id}")
    b.adjust(2)
    return b.as_markup()


def confirm_keyboard(draft_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Confirmar", callback_data=f"{CB_CONFIRM}:{draft_id}")
    b.button(text="📅 Mudar data", callback_data=f"{CB_CHANGE_DATE}:{draft_id}")
    b.button(text="✖️ Cancelar", callback_data=f"{CB_CANCEL}:{draft_id}")
    b.adjust(1, 2)
    return b.as_markup()


def dates_keyboard(draft_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for label, days in (("Hoje", 0), ("Ontem", 1), ("Anteontem", 2)):
        b.button(text=label, callback_data=f"{CB_DATE}:{draft_id}:{days}")
    b.button(text="📅 Outra data", callback_data=f"{CB_FREE_DATE}:{draft_id}")
    b.button(text="✖️ Cancelar", callback_data=f"{CB_CANCEL}:{draft_id}")
    b.adjust(3, 1, 1)
    return b.as_markup()


def undo_keyboard(transaction_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="↩️ Desfazer", callback_data=f"{CB_UNDO}:{transaction_id}")
    return b.as_markup()
