"""Data model.

Decisions worth remembering:
- amount is always POSITIVE, in cents; the sign comes from `kind`.
- `date` is when it happened (local timezone); `created_at` is when it was
  recorded (UTC).
- `source_update_id` is UNIQUE: that is the defense against Telegram resending
  an update.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

EXPENSE = "expense"
INCOME = "income"
BOTH = "both"


class Base(DeclarativeBase):
    pass


class Category(Base):
    __tablename__ = "category"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('expense','income','both')", name="ck_category_kind"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)
    kind: Mapped[str] = mapped_column(String(10))
    active: Mapped[bool] = mapped_column(default=True)

    def accepts(self, kind: str) -> bool:
        return self.kind == BOTH or self.kind == kind


class Transaction(Base):
    __tablename__ = "transaction"
    __table_args__ = (
        CheckConstraint("kind IN ('expense','income')", name="ck_transaction_kind"),
        CheckConstraint("amount_cents > 0", name="ck_transaction_amount_positive"),
        Index("idx_transaction_date", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))
    amount_cents: Mapped[int] = mapped_column(Integer)
    date: Mapped[dt.date] = mapped_column(Date)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("category.id"))
    # Reserved for v2 (wallet, Nubank, ...). Not used yet.
    account_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    source_update_id: Mapped[int | None] = mapped_column(
        Integer, unique=True, nullable=True
    )

    category: Mapped[Category | None] = relationship(lazy="joined")


class Draft(Base):
    """An entry being built by the guided flow.

    It lives in the database (not in memory) for two reasons: it survives a
    restart, and its short `id` is what travels in the buttons' callback_data,
    which solves the problem of a button clicked days later.
    """

    __tablename__ = "draft"

    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    state: Mapped[str] = mapped_column(String(20))
    chat_id: Mapped[int] = mapped_column(Integer)
    message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    kind: Mapped[str | None] = mapped_column(String(10), nullable=True)
    amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("category.id"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )


# States of the guided flow.
S_KIND = "kind"
S_AMOUNT = "amount"
S_CATEGORY = "category"
S_CONFIRM = "confirm"
S_FREE_DATE = "free_date"
