from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from caderneta.core import (
    DEFAULT_CATEGORIES,
    InvalidAmountError,
    find_category_by_name,
    list_categories,
    month_range,
    record_transaction,
    seed_categories,
    summary,
    undo_last,
)
from caderneta.models import EXPENSE, INCOME

TODAY = dt.date(2026, 8, 18)


def test_seed_is_idempotent(session: Session) -> None:
    assert seed_categories(session) == len(DEFAULT_CATEGORIES)
    assert seed_categories(session) == 0
    assert len(list_categories(session)) == len(DEFAULT_CATEGORIES)


def test_list_categories_filters_by_kind(session: Session) -> None:
    seed_categories(session)
    names = {c.name for c in list_categories(session, kind=INCOME)}
    assert "Salário" in names
    assert "Mercado" not in names
    # 'Outros' is kind BOTH: it shows up in both.
    assert "Outros" in names


def test_find_category_by_prefix(session: Session) -> None:
    seed_categories(session)
    assert find_category_by_name(session, "merc").name == "Mercado"
    assert find_category_by_name(session, "MERCADO").name == "Mercado"
    assert find_category_by_name(session, "xyz") is None


def test_ambiguous_prefix_does_not_guess(session: Session) -> None:
    seed_categories(session)
    # "Salário" and "Saúde" both start with "sa": ambiguous, better not to guess.
    assert find_category_by_name(session, "sa") is None


def test_record_transaction(session: Session) -> None:
    t, created = record_transaction(
        session, kind=EXPENSE, amount_cents=5000, date=TODAY, description="pão"
    )
    assert created is True
    assert t.id is not None
    assert t.amount_cents == 5000


def test_zero_or_negative_amount_is_rejected(session: Session) -> None:
    with pytest.raises(InvalidAmountError):
        record_transaction(session, kind=EXPENSE, amount_cents=0, date=TODAY)
    with pytest.raises(InvalidAmountError):
        record_transaction(session, kind=EXPENSE, amount_cents=-1, date=TODAY)


def test_same_update_id_does_not_duplicate(session: Session) -> None:
    """Telegram resends updates. Without this, one expense becomes two."""
    first, created1 = record_transaction(
        session, kind=EXPENSE, amount_cents=5000, date=TODAY, source_update_id=999
    )
    second, created2 = record_transaction(
        session, kind=EXPENSE, amount_cents=5000, date=TODAY, source_update_id=999
    )
    assert created1 is True
    assert created2 is False
    assert first.id == second.id
    assert summary(session, TODAY, TODAY).total_expense == 5000


def test_null_update_id_does_not_block_repeats(session: Session) -> None:
    # Two R$ 5 coffees on the same day are two legitimate entries.
    record_transaction(session, kind=EXPENSE, amount_cents=500, date=TODAY)
    record_transaction(session, kind=EXPENSE, amount_cents=500, date=TODAY)
    assert summary(session, TODAY, TODAY).total_expense == 1000


def test_summary_balance_and_categories(session: Session) -> None:
    seed_categories(session)
    market = find_category_by_name(session, "Mercado")
    salary = find_category_by_name(session, "Salário")

    record_transaction(
        session, kind=INCOME, amount_cents=300000, date=TODAY,
        category_id=salary.id,
    )
    record_transaction(
        session, kind=EXPENSE, amount_cents=5000, date=TODAY, category_id=market.id
    )
    record_transaction(
        session, kind=EXPENSE, amount_cents=2500, date=TODAY, category_id=market.id
    )

    s = summary(session, TODAY, TODAY)
    assert s.total_income == 300000
    assert s.total_expense == 7500
    assert s.balance == 292500
    assert len(s.expenses_by_category) == 1
    assert s.expenses_by_category[0].name == "Mercado"
    assert s.expenses_by_category[0].count == 2


def test_summary_respects_the_range(session: Session) -> None:
    record_transaction(session, kind=EXPENSE, amount_cents=1000, date=TODAY)
    record_transaction(
        session, kind=EXPENSE, amount_cents=9999, date=dt.date(2026, 7, 31)
    )
    start, end = month_range(TODAY)
    assert summary(session, start, end).total_expense == 1000


def test_empty_summary(session: Session) -> None:
    s = summary(session, TODAY, TODAY)
    assert s.empty is True
    assert s.balance == 0


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (dt.date(2026, 8, 18), (dt.date(2026, 8, 1), dt.date(2026, 8, 31))),
        (dt.date(2026, 2, 10), (dt.date(2026, 2, 1), dt.date(2026, 2, 28))),
        (dt.date(2024, 2, 10), (dt.date(2024, 2, 1), dt.date(2024, 2, 29))),
        (dt.date(2026, 12, 5), (dt.date(2026, 12, 1), dt.date(2026, 12, 31))),
    ],
)
def test_month_range(day: dt.date, expected: tuple[dt.date, dt.date]) -> None:
    assert month_range(day) == expected


def test_undo_removes_the_last_one(session: Session) -> None:
    seed_categories(session)
    market = find_category_by_name(session, "Mercado")
    record_transaction(session, kind=EXPENSE, amount_cents=1000, date=TODAY)
    record_transaction(
        session, kind=EXPENSE, amount_cents=2000, date=TODAY, category_id=market.id
    )

    removed = undo_last(session)
    assert removed is not None
    assert removed.amount_cents == 2000
    assert removed.category == "Mercado"
    assert summary(session, TODAY, TODAY).total_expense == 1000


def test_undo_with_nothing(session: Session) -> None:
    assert undo_last(session) is None
