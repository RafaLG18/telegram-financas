"""Message rendering. Kept out of the handlers to make tweaking the tone easy.

The strings below are what the user reads in Telegram, so they stay in pt-BR.
"""

from __future__ import annotations

import datetime as dt

from .core import RemovedTransaction, Summary
from .models import EXPENSE, INCOME, Draft, Transaction
from .parse import OLD_DATE_DAYS, format_amount

_ICON = {EXPENSE: "🔴", INCOME: "🟢"}
_LABEL = {EXPENSE: "Gasto", INCOME: "Entrada"}


def friendly_date(date: dt.date, today: dt.date) -> str:
    delta = (today - date).days
    if delta == 0:
        return "hoje"
    if delta == 1:
        return "ontem"
    if delta == 2:
        return "anteontem"
    return date.strftime("%d/%m/%Y")


def transaction_line(
    kind: str,
    amount_cents: int,
    date: dt.date,
    category: str | None,
    description: str | None,
    today: dt.date,
) -> str:
    parts = [
        f"{_ICON.get(kind, '•')} <b>{_LABEL.get(kind, kind)}</b>",
        f"<b>{format_amount(amount_cents)}</b>",
        category or "sem categoria",
        friendly_date(date, today),
    ]
    text = " · ".join(parts)
    if description:
        text += f"\n<i>{description}</i>"
    return text


def transaction_recorded(t: Transaction, today: dt.date) -> str:
    return "Registrado.\n\n" + transaction_line(
        t.kind,
        t.amount_cents,
        t.date,
        t.category.name if t.category else None,
        t.description,
        today,
    )


def transaction_removed(t: RemovedTransaction, today: dt.date) -> str:
    return "Desfeito. Removi:\n\n" + transaction_line(
        t.kind, t.amount_cents, t.date, t.category, t.description, today
    )


def draft_preview(d: Draft, category: str | None, today: dt.date) -> str:
    assert d.kind is not None and d.amount_cents is not None
    date = d.date or today
    text = "Confere?\n\n" + transaction_line(
        d.kind, d.amount_cents, date, category, d.description, today
    )
    # The preview is already the confirmation: instead of an extra question, a
    # very old date is flagged right here - getting the year wrong is easy.
    if (today - date).days > OLD_DATE_DAYS:
        text += "\n\n⚠️ <i>Essa data é de mais de 2 anos atrás. Confere o ano?</i>"
    return text


def render_summary(s: Summary, title: str) -> str:
    if s.empty:
        return f"<b>{title}</b>\n\nNenhum lançamento no período."

    lines = [f"<b>{title}</b>", ""]
    lines.append(f"🟢 Entradas: <b>{format_amount(s.total_income)}</b>")
    lines.append(f"🔴 Gastos: <b>{format_amount(s.total_expense)}</b>")
    sign = "🟢" if s.balance >= 0 else "🔴"
    lines.append(f"{sign} Saldo: <b>{format_amount(s.balance)}</b>")

    if s.expenses_by_category:
        lines.append("")
        lines.append("<b>Gastos por categoria</b>")
        for line in s.expenses_by_category:
            share = (
                f" ({line.total_cents * 100 // s.total_expense}%)"
                if s.total_expense
                else ""
            )
            lines.append(
                f"• {line.name}: {format_amount(line.total_cents)}{share}"
                f" — {line.count}x"
            )

    return "\n".join(lines)


HELP = """<b>Caderneta</b> — controle financeiro

<b>Registrar</b>
/registrar — fluxo guiado com botões (dá para escolher qualquer data)
Ou mande direto: <code>50 mercado</code>, <code>1.250,00 aluguel ontem</code>

<b>Consultar</b>
/hoje — resumo do dia
/mes — resumo do mês
/extrato — últimos lançamentos

<b>Corrigir</b>
/desfazer — remove o último lançamento
/cancelar — descarta um registro em andamento

<b>Categorias</b>
/categorias — lista as disponíveis"""
