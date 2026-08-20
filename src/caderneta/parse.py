"""Free-text parsing: amount, date and description.

No LLM: explicit rules, deterministic and testable. The guided flow is still the
main path; this is the shortcut for daily use.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

_ONLY_NUMBER = re.compile(r"\d[\d.,]*")
_DATE_BR = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")


def parse_amount(text: str) -> int | None:
    """Convert '50', '50,90', 'R$ 1.250,00' into cents. None if not an amount."""
    t = text.strip().lower().replace("r$", "").replace(" ", "")
    if not t or not _ONLY_NUMBER.fullmatch(t):
        return None

    has_comma, has_dot = "," in t, "." in t

    if has_comma and has_dot:
        # The rightmost separator is the decimal one.
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    elif has_comma:
        if t.count(",") > 1:
            return None
        t = t.replace(",", ".")
    elif has_dot:
        parts = t.split(".")
        plain_decimal = len(parts) == 2 and len(parts[1]) in (1, 2)
        if not plain_decimal:
            # Only accepted as a thousands separator if every group has 3 digits.
            if not all(len(p) == 3 for p in parts[1:]):
                return None
            t = t.replace(".", "")

    try:
        amount = Decimal(t)
    except InvalidOperation:
        return None

    if amount <= 0:
        return None

    cents = int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return cents or None


def parse_date(text: str, today: dt.date) -> tuple[dt.date | None, str]:
    """Extract a relative or dd/mm date. Returns (date, text_without_the_date)."""
    t = text.strip()
    lower = t.lower()

    for term, delta in (("anteontem", 2), ("ontem", 1), ("hoje", 0)):
        if re.search(rf"\b{term}\b", lower):
            rest = re.sub(rf"\b{term}\b", " ", lower, count=1)
            return today - dt.timedelta(days=delta), " ".join(rest.split())

    found = _DATE_BR.search(t)
    if found:
        day, month, year = found.group(1), found.group(2), found.group(3)
        try:
            if year is None:
                candidate = dt.date(today.year, int(month), int(day))
                # 31/12 recorded on 02/01 is almost certainly from last year.
                if (candidate - today).days > 180:
                    candidate = candidate.replace(year=today.year - 1)
            else:
                y = int(year)
                candidate = dt.date(2000 + y if y < 100 else y, int(month), int(day))
        except ValueError:
            return None, t
        rest = (t[: found.start()] + " " + t[found.end() :]).strip()
        return candidate, " ".join(rest.split())

    return None, t


# Past this limit the date is still valid, but it deserves a warning in the
# preview: getting the year wrong in `15/08/2015` is far too easy to accept
# silently.
OLD_DATE_DAYS = 730

DATE_OK = "ok"
DATE_UNPARSED = "unparsed"
DATE_FUTURE = "future"


@dataclass(frozen=True)
class ParsedDate:
    """Result of `parse_strict_date`. `date` is only set when reason=DATE_OK."""

    date: dt.date | None
    reason: str


def parse_strict_date(text: str, today: dt.date) -> ParsedDate:
    """Read a message that must be *entirely* a date.

    Unlike `parse_date`, which digs a date out of a sentence, here leftover text
    is an error: someone typing while in the date state is not describing the
    expense. The reason comes back too because the handler needs to say different
    things for "I did not understand" and for "that is in the future".
    """
    t = text.strip()
    if not t:
        return ParsedDate(None, DATE_UNPARSED)

    date, rest = parse_date(t, today)
    if date is None or rest:
        return ParsedDate(None, DATE_UNPARSED)
    if date > today:
        return ParsedDate(None, DATE_FUTURE)
    return ParsedDate(date, DATE_OK)


@dataclass(frozen=True)
class QuickEntry:
    amount_cents: int
    description: str
    date: dt.date


def parse_entry(text: str, today: dt.date) -> QuickEntry | None:
    """'50 mercado', 'mercado 50', '1.250,00 aluguel ontem' -> QuickEntry."""
    date, rest = parse_date(text, today)
    tokens = rest.split()
    if not tokens:
        return None

    for i, token in enumerate(tokens):
        cents = parse_amount(token)
        if cents is not None:
            description = " ".join(tokens[:i] + tokens[i + 1 :]).strip()
            return QuickEntry(cents, description, date or today)

    return None


def format_amount(cents: int) -> str:
    whole, rest = divmod(abs(cents), 100)
    thousands = f"{whole:,}".replace(",", ".")
    sign = "-" if cents < 0 else ""
    return f"{sign}R$ {thousands},{rest:02d}"
