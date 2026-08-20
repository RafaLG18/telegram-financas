"""Guided flow: /registrar -> kind -> amount -> category -> confirmation."""

from __future__ import annotations

import datetime as dt
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, Filter
from aiogram.types import CallbackQuery, Message
from sqlalchemy.orm import Session

from ..config import Config
from ..core import (
    active_draft,
    clear_chat_drafts,
    discard_draft,
    finish_draft,
    get_draft,
    list_categories,
    new_draft,
)
from ..db import session_scope
from ..keyboards import (
    CB_CANCEL,
    CB_CATEGORY,
    CB_CHANGE_DATE,
    CB_CONFIRM,
    CB_DATE,
    CB_FREE_DATE,
    CB_KIND,
    categories_keyboard,
    confirm_keyboard,
    dates_keyboard,
    kind_keyboard,
)
from ..models import (
    Draft,
    EXPENSE,
    S_AMOUNT,
    S_CATEGORY,
    S_CONFIRM,
    S_FREE_DATE,
    S_KIND,
)
from ..parse import DATE_FUTURE, parse_amount, parse_strict_date
from ..texts import draft_preview, transaction_recorded

log = logging.getLogger(__name__)
router = Router(name="record")

_EXPIRED = "Esse lançamento já foi finalizado ou cancelado. Mande /registrar de novo."
_ASK_DATE = (
    "Qual a data? Ex: <code>15/08</code>, <code>15/08/2025</code> ou "
    "<code>ontem</code>.\n\nOu /cancelar."
)


async def _clear_keyboard(callback: CallbackQuery, text: str) -> None:
    """Edit the message removing the buttons - kills the 'zombie button'."""
    try:
        await callback.message.edit_text(text, reply_markup=None)  # type: ignore[union-attr]
    except (TelegramBadRequest, AttributeError):
        log.debug("could not edit the callback message", exc_info=True)


def _did(callback: CallbackQuery) -> str:
    """The draft id carried by the callback_data."""
    return (callback.data or "").split(":")[1]


def _preview(session: Session, draft: Draft, today: dt.date) -> str:
    name = next(
        (c.name for c in list_categories(session) if c.id == draft.category_id),
        None,
    )
    return draft_preview(draft, name, today)


class _AwaitingText(Filter):
    """Matches any text while the active draft is in the expected state."""

    state: str

    async def __call__(self, message: Message) -> bool | dict:
        if not message.text or message.text.startswith("/"):
            return False
        with session_scope() as session:
            draft = active_draft(session, message.chat.id)
            if draft is not None and draft.state == self.state:
                return {"draft_id": draft.id}
        return False


class AwaitingAmount(_AwaitingText):
    state = S_AMOUNT


class AwaitingDate(_AwaitingText):
    state = S_FREE_DATE


@router.message(Command("registrar", "novo"))
async def cmd_record(message: Message) -> None:
    with session_scope() as session:
        clear_chat_drafts(session, message.chat.id)
        draft = new_draft(session, chat_id=message.chat.id, state=S_KIND)
        draft_id = draft.id

    sent = await message.answer(
        "O que você quer registrar?", reply_markup=kind_keyboard(draft_id)
    )

    with session_scope() as session:
        draft = get_draft(session, draft_id)
        if draft is not None:
            draft.message_id = sent.message_id


@router.message(Command("cancelar"))
async def cmd_cancel(message: Message) -> None:
    with session_scope() as session:
        removed = clear_chat_drafts(session, message.chat.id)
    await message.answer(
        "Registro em andamento descartado." if removed else "Nada em andamento."
    )


@router.callback_query(F.data.startswith(f"{CB_KIND}:"))
async def chose_kind(callback: CallbackQuery) -> None:
    await callback.answer()
    draft_id = _did(callback)
    kind = (callback.data or "").split(":")[2]

    with session_scope() as session:
        draft = get_draft(session, draft_id)
        if draft is None:
            await _clear_keyboard(callback, _EXPIRED)
            return
        draft.kind = kind
        draft.state = S_AMOUNT

    label = "gasto" if kind == EXPENSE else "entrada"
    await _clear_keyboard(
        callback,
        f"Qual o valor do {label}?\n\n"
        "<i>Pode mandar só o número (50) ou já com a descrição "
        "(50 pão na padaria).</i>",
    )


@router.message(AwaitingAmount())
async def got_amount(message: Message, draft_id: str, config: Config) -> None:
    text = (message.text or "").strip()
    parts = text.split(maxsplit=1)
    amount = parse_amount(parts[0]) if parts else None

    if amount is None:
        await message.answer(
            "Não entendi esse valor. Tente <code>50</code>, <code>50,90</code> "
            "ou <code>1.250,00</code>.\n\nOu /cancelar."
        )
        return

    description = parts[1] if len(parts) > 1 else None

    with session_scope() as session:
        draft = get_draft(session, draft_id)
        if draft is None:
            await message.answer(_EXPIRED)
            return
        draft.amount_cents = amount
        draft.description = description
        draft.state = S_CATEGORY
        draft.date = dt.datetime.now(config.tz).date()
        categories = list_categories(session, kind=draft.kind)

    await message.answer(
        "Qual categoria?", reply_markup=categories_keyboard(draft_id, categories)
    )


@router.callback_query(F.data.startswith(f"{CB_CATEGORY}:"))
async def chose_category(callback: CallbackQuery, config: Config) -> None:
    await callback.answer()
    draft_id = _did(callback)
    category_id = int((callback.data or "").split(":")[2])
    today = dt.datetime.now(config.tz).date()

    with session_scope() as session:
        draft = get_draft(session, draft_id)
        if draft is None:
            await _clear_keyboard(callback, _EXPIRED)
            return
        draft.category_id = category_id
        draft.state = S_CONFIRM
        text = _preview(session, draft, today)

    try:
        await callback.message.edit_text(  # type: ignore[union-attr]
            text, reply_markup=confirm_keyboard(draft_id)
        )
    except (TelegramBadRequest, AttributeError):
        log.debug("failed to edit the preview", exc_info=True)


@router.callback_query(F.data.startswith(f"{CB_CHANGE_DATE}:"))
async def asked_to_change_date(callback: CallbackQuery) -> None:
    await callback.answer()
    draft_id = _did(callback)

    with session_scope() as session:
        if get_draft(session, draft_id) is None:
            await _clear_keyboard(callback, _EXPIRED)
            return

    try:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "Quando foi?", reply_markup=dates_keyboard(draft_id)
        )
    except (TelegramBadRequest, AttributeError):
        log.debug("failed to edit the date picker", exc_info=True)


@router.callback_query(F.data.startswith(f"{CB_DATE}:"))
async def chose_date(callback: CallbackQuery, config: Config) -> None:
    await callback.answer()
    draft_id = _did(callback)
    days = int((callback.data or "").split(":")[2])
    today = dt.datetime.now(config.tz).date()

    with session_scope() as session:
        draft = get_draft(session, draft_id)
        if draft is None:
            await _clear_keyboard(callback, _EXPIRED)
            return
        draft.date = today - dt.timedelta(days=days)
        draft.state = S_CONFIRM
        text = _preview(session, draft, today)

    try:
        await callback.message.edit_text(  # type: ignore[union-attr]
            text, reply_markup=confirm_keyboard(draft_id)
        )
    except (TelegramBadRequest, AttributeError):
        log.debug("failed to go back to the preview", exc_info=True)


@router.callback_query(F.data.startswith(f"{CB_FREE_DATE}:"))
async def asked_for_free_date(callback: CallbackQuery) -> None:
    await callback.answer()
    draft_id = _did(callback)

    with session_scope() as session:
        draft = get_draft(session, draft_id)
        if draft is None:
            await _clear_keyboard(callback, _EXPIRED)
            return
        draft.state = S_FREE_DATE

    await _clear_keyboard(callback, _ASK_DATE)


@router.message(AwaitingDate())
async def got_date(message: Message, draft_id: str, config: Config) -> None:
    today = dt.datetime.now(config.tz).date()
    parsed = parse_strict_date(message.text or "", today)

    if parsed.date is None:
        # The draft is left untouched: the amount and category already typed
        # stay alive and the next message lands here again.
        await message.answer(
            "Essa data ainda não aconteceu. Lançamento é fato ocorrido — "
            "manda uma data de hoje ou de antes.\n\nOu /cancelar."
            if parsed.reason == DATE_FUTURE
            else f"Não entendi essa data.\n\n{_ASK_DATE}"
        )
        return

    with session_scope() as session:
        draft = get_draft(session, draft_id)
        if draft is None:
            await message.answer(_EXPIRED)
            return
        draft.date = parsed.date
        draft.state = S_CONFIRM
        text = _preview(session, draft, today)

    await message.answer(text, reply_markup=confirm_keyboard(draft_id))


@router.callback_query(F.data.startswith(f"{CB_CONFIRM}:"))
async def confirmed(callback: CallbackQuery, config: Config) -> None:
    await callback.answer("Registrando…")
    draft_id = _did(callback)
    today = dt.datetime.now(config.tz).date()

    with session_scope() as session:
        draft = get_draft(session, draft_id)
        if draft is None:
            # Double click or an old button: the first click already saved it.
            await _clear_keyboard(callback, _EXPIRED)
            return
        transaction = finish_draft(session, draft)
        text = transaction_recorded(transaction, today)

    await _clear_keyboard(callback, text)


@router.callback_query(F.data.startswith(f"{CB_CANCEL}:"))
async def cancelled(callback: CallbackQuery) -> None:
    await callback.answer("Cancelado")
    draft_id = _did(callback)
    with session_scope() as session:
        discard_draft(session, draft_id)
    await _clear_keyboard(callback, "Cancelado, nada foi registrado.")
