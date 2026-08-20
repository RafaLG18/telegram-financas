"""Draft: the entry being built by the guided flow.

It lives in the database, not in memory - it survives a restart, and its short
id is what travels in the buttons' callback_data.
"""

from __future__ import annotations

import datetime as dt
import secrets

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import Draft, Transaction
from .transactions import record_transaction


def new_draft(session: Session, *, chat_id: int, state: str) -> Draft:
    draft = Draft(id=secrets.token_hex(4), chat_id=chat_id, state=state)
    session.add(draft)
    session.flush()
    return draft


def get_draft(session: Session, draft_id: str) -> Draft | None:
    return session.get(Draft, draft_id)


def active_draft(session: Session, chat_id: int) -> Draft | None:
    return session.scalar(
        select(Draft)
        .where(Draft.chat_id == chat_id)
        .order_by(Draft.created_at.desc())
        .limit(1)
    )


def discard_draft(session: Session, draft_id: str) -> None:
    session.execute(delete(Draft).where(Draft.id == draft_id))


def clear_chat_drafts(session: Session, chat_id: int) -> int:
    result = session.execute(delete(Draft).where(Draft.chat_id == chat_id))
    return result.rowcount or 0


def purge_old_drafts(session: Session, hours: int = 24) -> int:
    cutoff = dt.datetime.utcnow() - dt.timedelta(hours=hours)
    result = session.execute(delete(Draft).where(Draft.created_at < cutoff))
    return result.rowcount or 0


def finish_draft(
    session: Session, draft: Draft, *, source_update_id: int | None = None
) -> Transaction:
    """Turn a complete draft into a transaction and discard the draft."""
    if draft.kind is None or draft.amount_cents is None:
        raise ValueError("incomplete draft")

    transaction, _ = record_transaction(
        session,
        kind=draft.kind,
        amount_cents=draft.amount_cents,
        date=draft.date or dt.date.today(),
        category_id=draft.category_id,
        description=draft.description,
        source_update_id=source_update_id,
    )
    discard_draft(session, draft.id)
    return transaction
