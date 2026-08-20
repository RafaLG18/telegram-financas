"""Free-text shortcut: '50 mercado' becomes an entry straight away.

Last in the router chain: it only gets what nobody else wanted.
"""

from __future__ import annotations

import datetime as dt
import logging

from aiogram import F, Router
from aiogram.types import Message

from ..config import Config
from ..core import find_category_by_name, record_transaction
from ..db import session_scope
from ..keyboards import undo_keyboard
from ..models import EXPENSE, INCOME
from ..parse import parse_entry
from ..texts import transaction_recorded

log = logging.getLogger(__name__)
router = Router(name="quick")

_INCOME_WORDS = ("recebi", "salario", "salário", "entrada", "rendimento")

_NOT_UNDERSTOOD = (
    "Não entendi.\n\n"
    "Mande algo como <code>50 mercado</code> ou <code>1.250,00 aluguel ontem</code>.\n"
    "Para entrada, comece com <code>+</code>: <code>+3000 salário</code>.\n\n"
    "Ou use /registrar para o passo a passo."
)


def _detect_kind(text: str) -> tuple[str, str]:
    """Returns (kind, text_without_the_marker)."""
    clean = text.strip()
    if clean.startswith("+"):
        return INCOME, clean[1:].strip()
    if clean.startswith("-"):
        return EXPENSE, clean[1:].strip()
    if any(w in clean.lower() for w in _INCOME_WORDS):
        return INCOME, clean
    return EXPENSE, clean


@router.message(F.text & ~F.text.startswith("/"))
async def free_text(message: Message, config: Config, update_id: int) -> None:
    today = dt.datetime.now(config.tz).date()
    kind, text = _detect_kind(message.text or "")

    entry = parse_entry(text, today)
    if entry is None:
        await message.answer(_NOT_UNDERSTOOD)
        return

    with session_scope() as session:
        category = find_category_by_name(session, entry.description)
        if category is None and entry.description:
            first_word = entry.description.split()[0]
            category = find_category_by_name(session, first_word)

        transaction, created = record_transaction(
            session,
            kind=kind,
            amount_cents=entry.amount_cents,
            date=entry.date,
            category_id=category.id if category else None,
            description=entry.description or None,
            source_update_id=update_id,
        )
        reply = transaction_recorded(transaction, today)
        transaction_id = transaction.id

    if not created:
        # Update resent by Telegram: we neither duplicate nor confuse the user.
        log.info("update %s already processed, ignoring resend", update_id)
        return

    await message.answer(reply, reply_markup=undo_keyboard(transaction_id))
