"""Renderizacao das mensagens. Separado dos handlers pra facilitar ajuste de tom."""

from __future__ import annotations

import datetime as dt

from .core import Resumo, TransacaoRemovida
from .models import ENTRADA, GASTO, Rascunho, Transacao
from .parse import formata_valor

_ICONE = {GASTO: "🔴", ENTRADA: "🟢"}
_ROTULO = {GASTO: "Gasto", ENTRADA: "Entrada"}


def data_amigavel(data: dt.date, hoje: dt.date) -> str:
    delta = (hoje - data).days
    if delta == 0:
        return "hoje"
    if delta == 1:
        return "ontem"
    if delta == 2:
        return "anteontem"
    return data.strftime("%d/%m/%Y")


def linha_transacao(
    tipo: str,
    valor_centavos: int,
    data: dt.date,
    categoria: str | None,
    descricao: str | None,
    hoje: dt.date,
) -> str:
    partes = [
        f"{_ICONE.get(tipo, '•')} <b>{_ROTULO.get(tipo, tipo)}</b>",
        f"<b>{formata_valor(valor_centavos)}</b>",
        categoria or "sem categoria",
        data_amigavel(data, hoje),
    ]
    texto = " · ".join(partes)
    if descricao:
        texto += f"\n<i>{descricao}</i>"
    return texto


def transacao_registrada(t: Transacao, hoje: dt.date) -> str:
    return "Registrado.\n\n" + linha_transacao(
        t.tipo,
        t.valor_centavos,
        t.data,
        t.categoria.nome if t.categoria else None,
        t.descricao,
        hoje,
    )


def transacao_removida(t: TransacaoRemovida, hoje: dt.date) -> str:
    return "Desfeito. Removi:\n\n" + linha_transacao(
        t.tipo, t.valor_centavos, t.data, t.categoria, t.descricao, hoje
    )


def previa_rascunho(r: Rascunho, categoria: str | None, hoje: dt.date) -> str:
    assert r.tipo is not None and r.valor_centavos is not None
    return "Confere?\n\n" + linha_transacao(
        r.tipo, r.valor_centavos, r.data or hoje, categoria, r.descricao, hoje
    )


def render_resumo(r: Resumo, titulo: str) -> str:
    if r.vazio:
        return f"<b>{titulo}</b>\n\nNenhum lançamento no período."

    linhas = [f"<b>{titulo}</b>", ""]
    linhas.append(f"🟢 Entradas: <b>{formata_valor(r.total_entrada)}</b>")
    linhas.append(f"🔴 Gastos: <b>{formata_valor(r.total_gasto)}</b>")
    sinal = "🟢" if r.saldo >= 0 else "🔴"
    linhas.append(f"{sinal} Saldo: <b>{formata_valor(r.saldo)}</b>")

    if r.gastos_por_categoria:
        linhas.append("")
        linhas.append("<b>Gastos por categoria</b>")
        for linha in r.gastos_por_categoria:
            fatia = (
                f" ({linha.total_centavos * 100 // r.total_gasto}%)"
                if r.total_gasto
                else ""
            )
            linhas.append(
                f"• {linha.nome}: {formata_valor(linha.total_centavos)}{fatia}"
                f" — {linha.quantidade}x"
            )

    return "\n".join(linhas)


AJUDA = """<b>Caderneta</b> — controle financeiro

<b>Registrar</b>
/registrar — fluxo guiado com botões
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
