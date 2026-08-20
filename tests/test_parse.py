from __future__ import annotations

import datetime as dt

import pytest

from caderneta.parse import (
    DATE_FUTURE,
    DATE_OK,
    DATE_UNPARSED,
    format_amount,
    parse_amount,
    parse_date,
    parse_entry,
    parse_strict_date,
)

TODAY = dt.date(2026, 8, 18)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("50", 5000),
        ("50,90", 5090),
        ("50.90", 5090),
        ("50,9", 5090),
        ("R$ 50", 5000),
        ("r$50,00", 5000),
        ("1.250,00", 125000),
        ("1250", 125000),
        ("1.250", 125000),
        ("0,01", 1),
        ("1.234.567,89", 123456789),
    ],
)
def test_parse_amount_accepted_formats(text: str, expected: int) -> None:
    assert parse_amount(text) == expected


@pytest.mark.parametrize(
    "text", ["", "mercado", "0", "0,00", "-50", "50,00,00", "1.2345", "abc50"]
)
def test_parse_amount_rejects(text: str) -> None:
    assert parse_amount(text) is None


def test_ambiguous_dot_resolved_by_group_size() -> None:
    # A 3-digit group is thousands; a 1-2 digit group is decimals.
    assert parse_amount("1.250") == 125000
    assert parse_amount("50.90") == 5090
    assert parse_amount("1.25") == 125


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ontem", dt.date(2026, 8, 17)),
        ("anteontem", dt.date(2026, 8, 16)),
        ("hoje", TODAY),
        ("15/08", dt.date(2026, 8, 15)),
        ("15/08/2025", dt.date(2025, 8, 15)),
    ],
)
def test_parse_date(text: str, expected: dt.date) -> None:
    date, _ = parse_date(f"mercado {text}", TODAY)
    assert date == expected


def test_distant_future_date_becomes_last_year() -> None:
    # In August, "31/12" with no year is this year, but "01/01" is already past.
    date, _ = parse_date("31/12", TODAY)
    assert date == dt.date(2026, 12, 31)


def test_invalid_date_does_not_break() -> None:
    date, rest = parse_date("32/13", TODAY)
    assert date is None
    assert "32/13" in rest


def test_parse_entry_amount_first() -> None:
    e = parse_entry("50 mercado", TODAY)
    assert e is not None
    assert e.amount_cents == 5000
    assert e.description == "mercado"
    assert e.date == TODAY


def test_parse_entry_amount_last() -> None:
    e = parse_entry("mercado 50", TODAY)
    assert e is not None
    assert e.amount_cents == 5000
    assert e.description == "mercado"


def test_parse_entry_with_relative_date() -> None:
    e = parse_entry("1.250,00 aluguel ontem", TODAY)
    assert e is not None
    assert e.amount_cents == 125000
    assert e.description == "aluguel"
    assert e.date == dt.date(2026, 8, 17)


def test_parse_entry_without_amount() -> None:
    assert parse_entry("bom dia", TODAY) is None


@pytest.mark.parametrize(
    ("cents", "expected"),
    [
        (5000, "R$ 50,00"),
        (5090, "R$ 50,90"),
        (1, "R$ 0,01"),
        (125000, "R$ 1.250,00"),
        (-5000, "-R$ 50,00"),
        (0, "R$ 0,00"),
    ],
)
def test_format_amount(cents: int, expected: str) -> None:
    assert format_amount(cents) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("15/08", dt.date(2026, 8, 15)),
        ("15/08/2025", dt.date(2025, 8, 15)),
        ("15/08/25", dt.date(2025, 8, 15)),
        ("  15/8  ", dt.date(2026, 8, 15)),
        ("ontem", dt.date(2026, 8, 17)),
        ("anteontem", dt.date(2026, 8, 16)),
        ("hoje", TODAY),
    ],
)
def test_parse_strict_date_accepts(text: str, expected: dt.date) -> None:
    parsed = parse_strict_date(text, TODAY)
    assert parsed.reason == DATE_OK
    assert parsed.date == expected


def test_parse_strict_date_turns_the_year() -> None:
    # 31/12 typed in January is from last year, not 11 months from now.
    parsed = parse_strict_date("31/12", dt.date(2026, 1, 5))
    assert parsed.date == dt.date(2025, 12, 31)


@pytest.mark.parametrize(
    "text",
    [
        "mercado",
        "",
        "   ",
        "30/02",
        "45/13",
        "15/08 mercado",  # leftover text: here the whole message must be the date
        "50",
    ],
)
def test_parse_strict_date_not_a_date(text: str) -> None:
    parsed = parse_strict_date(text, TODAY)
    assert parsed.reason == DATE_UNPARSED
    assert parsed.date is None


@pytest.mark.parametrize("text", ["19/08", "01/09", "15/08/2027"])
def test_parse_strict_date_refuses_future(text: str) -> None:
    parsed = parse_strict_date(text, TODAY)
    assert parsed.reason == DATE_FUTURE
    assert parsed.date is None
