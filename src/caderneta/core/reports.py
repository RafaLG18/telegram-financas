"""Aggregation by period.

Sums and percentages in integer arithmetic: the amount is in cents, so there is
no rounding to do along the way.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import EXPENSE, Category, Transaction


@dataclass
class CategoryLine:
    name: str
    total_cents: int
    count: int


@dataclass
class Summary:
    start: dt.date
    end: dt.date
    total_expense: int = 0
    total_income: int = 0
    expenses_by_category: list[CategoryLine] = field(default_factory=list)

    @property
    def balance(self) -> int:
        return self.total_income - self.total_expense

    @property
    def empty(self) -> bool:
        return self.total_expense == 0 and self.total_income == 0


def summary(session: Session, start: dt.date, end: dt.date) -> Summary:
    """Summary of the period [start, end], both inclusive."""
    result = Summary(start=start, end=end)

    totals = session.execute(
        select(Transaction.kind, func.sum(Transaction.amount_cents))
        .where(Transaction.date >= start, Transaction.date <= end)
        .group_by(Transaction.kind)
    ).all()
    for kind, total in totals:
        if kind == EXPENSE:
            result.total_expense = int(total or 0)
        else:
            result.total_income = int(total or 0)

    lines = session.execute(
        select(
            func.coalesce(Category.name, "Sem categoria"),
            func.sum(Transaction.amount_cents),
            func.count(Transaction.id),
        )
        .join(Category, Transaction.category_id == Category.id, isouter=True)
        .where(
            Transaction.date >= start,
            Transaction.date <= end,
            Transaction.kind == EXPENSE,
        )
        .group_by(Category.name)
        .order_by(func.sum(Transaction.amount_cents).desc())
    ).all()
    result.expenses_by_category = [
        CategoryLine(name=name, total_cents=int(total or 0), count=int(qty))
        for name, total, qty in lines
    ]
    return result


def month_range(day: dt.date) -> tuple[dt.date, dt.date]:
    start = day.replace(day=1)
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1)
    else:
        next_month = start.replace(month=start.month + 1)
    return start, next_month - dt.timedelta(days=1)
