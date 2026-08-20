"""Queries and corrections: /hoje, /mes, /extrato, /desfazer."""

from __future__ import annotations

import datetime as dt
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from ..config import Config
from ..core import delete_transaction, month_range, summary, undo_last
from ..db import session_scope
from ..keyboards import CB_UNDO
from ..models import Transaction
from ..texts import render_summary, transaction_line, transaction_removed

log = logging.getLogger(__name__)
router = Router(name="reports")

_MONTHS = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


@router.message(Command("hoje"))
async def cmd_today(message: Message, config: Config) -> None:
    today = dt.datetime.now(config.tz).date()
    with session_scope() as session:
        s = summary(session, today, today)
    await message.answer(render_summary(s, f"Hoje · {today.strftime('%d/%m')}"))


@router.message(Command("mes", "mês"))
async def cmd_month(message: Message, config: Config) -> None:
    today = dt.datetime.now(config.tz).date()
    start, end = month_range(today)
    with session_scope() as session:
        s = summary(session, start, end)
    title = f"{_MONTHS[today.month - 1].capitalize()} de {today.year}"
    await message.answer(render_summary(s, title))


@router.message(Command("extrato"))
async def cmd_statement(message: Message, config: Config) -> None:
    today = dt.datetime.now(config.tz).date()
    with session_scope() as session:
        transactions = list(
            session.scalars(
                select(Transaction).order_by(Transaction.id.desc()).limit(15)
            ).all()
        )
        lines = [
            transaction_line(
                t.kind,
                t.amount_cents,
                t.date,
                t.category.name if t.category else None,
                t.description,
                today,
            )
            for t in transactions
        ]

    if not lines:
        await message.answer("Nenhum lançamento ainda.")
        return

    await message.answer("<b>Últimos lançamentos</b>\n\n" + "\n\n".join(lines))


@router.message(Command("desfazer"))
async def cmd_undo(message: Message, config: Config) -> None:
    today = dt.datetime.now(config.tz).date()
    with session_scope() as session:
        removed = undo_last(session)
        text = (
            transaction_removed(removed, today)
            if removed is not None
            else "Não há lançamento para desfazer."
        )
    await message.answer(text)


@router.callback_query(F.data.startswith(f"{CB_UNDO}:"))
async def clicked_undo(callback: CallbackQuery) -> None:
    transaction_id = int((callback.data or "").split(":")[1])

    with session_scope() as session:
        deleted = delete_transaction(session, transaction_id)

    await callback.answer("Desfeito" if deleted else "Esse lançamento já não existe")
    try:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "Lançamento desfeito." if deleted else "Esse lançamento já foi removido.",
            reply_markup=None,
        )
    except (TelegramBadRequest, AttributeError):
        log.debug("failed to edit the undo message", exc_info=True)
