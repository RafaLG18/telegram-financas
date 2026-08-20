"""Categories: default catalog and forgiving lookup.

Part of the rules core: it does not know Telegram exists.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import BOTH, EXPENSE, INCOME, Category

# The names are what the user reads in the bot, so they stay in pt-BR.
DEFAULT_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("Mercado", EXPENSE),
    ("Transporte", EXPENSE),
    ("Casa", EXPENSE),
    ("Alimentação", EXPENSE),
    ("Saúde", EXPENSE),
    ("Lazer", EXPENSE),
    ("Salário", INCOME),
    ("Outras entradas", INCOME),
    ("Outros", BOTH),
)


def seed_categories(session: Session) -> int:
    """Insert the default categories that do not exist yet. Idempotent."""
    existing = set(session.scalars(select(Category.name)).all())
    new = [
        Category(name=name, kind=kind)
        for name, kind in DEFAULT_CATEGORIES
        if name not in existing
    ]
    session.add_all(new)
    session.flush()
    return len(new)


def list_categories(session: Session, kind: str | None = None) -> list[Category]:
    stmt = select(Category).where(Category.active.is_(True))
    if kind is not None:
        stmt = stmt.where(Category.kind.in_((kind, BOTH)))
    return list(session.scalars(stmt.order_by(Category.name)).all())


def find_category_by_name(session: Session, text: str) -> Category | None:
    """Forgiving match: case-insensitive, and accepts a prefix ('merc' -> Mercado)."""
    target = text.strip().lower()
    if not target:
        return None
    candidates = list_categories(session)
    for cat in candidates:
        if cat.name.lower() == target:
            return cat
    prefixes = [c for c in candidates if c.name.lower().startswith(target)]
    return prefixes[0] if len(prefixes) == 1 else None
