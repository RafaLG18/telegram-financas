"""Entries: record, query the last one, undo.

Part of the rules core: it does not know Telegram exists.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import EXPENSE, INCOME, Transaction


class InvalidAmountError(ValueError):
    pass


def record_transaction(
    session: Session,
    *,
    kind: str,
    amount_cents: int,
    date: dt.date,
    category_id: int | None = None,
    description: str | None = None,
    source_update_id: int | None = None,
) -> tuple[Transaction, bool]:
    """Record an entry.

    Returns (transaction, created). `created=False` means this update_id was
    already processed - an update resent by Telegram, not a new entry.
    """
    if kind not in (EXPENSE, INCOME):
        raise ValueError(f"invalid kind: {kind!r}")
    if amount_cents <= 0:
        raise InvalidAmountError("amount must be positive")

    if source_update_id is not None:
        existing = session.scalar(
            select(Transaction).where(
                Transaction.source_update_id == source_update_id
            )
        )
        if existing is not None:
            return existing, False

    transaction = Transaction(
        kind=kind,
        amount_cents=amount_cents,
        date=date,
        category_id=category_id,
        description=(description or "").strip() or None,
        source_update_id=source_update_id,
    )
    session.add(transaction)
    try:
        session.flush()
    except IntegrityError:
        # Race: another processing of the same update got there first.
        session.rollback()
        existing = session.scalar(
            select(Transaction).where(
                Transaction.source_update_id == source_update_id
            )
        )
        if existing is None:
            raise
        return existing, False

    return transaction, True


def last_transaction(session: Session) -> Transaction | None:
    return session.scalar(select(Transaction).order_by(Transaction.id.desc()).limit(1))


@dataclass(frozen=True)
class RemovedTransaction:
    id: int
    kind: str
    amount_cents: int
    date: dt.date
    category: str | None
    description: str | None


def undo_last(session: Session) -> RemovedTransaction | None:
    """Remove the last entry and return a copy of what was removed."""
    target = last_transaction(session)
    if target is None:
        return None
    copy = RemovedTransaction(
        id=target.id,
        kind=target.kind,
        amount_cents=target.amount_cents,
        date=target.date,
        category=target.category.name if target.category else None,
        description=target.description,
    )
    session.delete(target)
    session.flush()
    return copy


def delete_transaction(session: Session, transaction_id: int) -> bool:
    target = session.get(Transaction, transaction_id)
    if target is None:
        return False
    session.delete(target)
    session.flush()
    return True
