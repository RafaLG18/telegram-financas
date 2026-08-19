"""Agregacao por periodo.

Soma e percentual em aritmetica inteira: o valor e centavo, entao nao ha
arredondamento a fazer no meio do caminho.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import GASTO, Categoria, Transacao


@dataclass
class LinhaCategoria:
    nome: str
    total_centavos: int
    quantidade: int


@dataclass
class Resumo:
    inicio: dt.date
    fim: dt.date
    total_gasto: int = 0
    total_entrada: int = 0
    gastos_por_categoria: list[LinhaCategoria] = field(default_factory=list)

    @property
    def saldo(self) -> int:
        return self.total_entrada - self.total_gasto

    @property
    def vazio(self) -> bool:
        return self.total_gasto == 0 and self.total_entrada == 0


def resumo(sessao: Session, inicio: dt.date, fim: dt.date) -> Resumo:
    """Resumo do periodo [inicio, fim], ambos inclusivos."""
    r = Resumo(inicio=inicio, fim=fim)

    totais = sessao.execute(
        select(Transacao.tipo, func.sum(Transacao.valor_centavos))
        .where(Transacao.data >= inicio, Transacao.data <= fim)
        .group_by(Transacao.tipo)
    ).all()
    for tipo, total in totais:
        if tipo == GASTO:
            r.total_gasto = int(total or 0)
        else:
            r.total_entrada = int(total or 0)

    linhas = sessao.execute(
        select(
            func.coalesce(Categoria.nome, "Sem categoria"),
            func.sum(Transacao.valor_centavos),
            func.count(Transacao.id),
        )
        .join(Categoria, Transacao.categoria_id == Categoria.id, isouter=True)
        .where(
            Transacao.data >= inicio,
            Transacao.data <= fim,
            Transacao.tipo == GASTO,
        )
        .group_by(Categoria.nome)
        .order_by(func.sum(Transacao.valor_centavos).desc())
    ).all()
    r.gastos_por_categoria = [
        LinhaCategoria(nome=nome, total_centavos=int(total or 0), quantidade=int(qtd))
        for nome, total, qtd in linhas
    ]
    return r


def intervalo_do_mes(dia: dt.date) -> tuple[dt.date, dt.date]:
    inicio = dia.replace(day=1)
    if inicio.month == 12:
        proximo = inicio.replace(year=inicio.year + 1, month=1)
    else:
        proximo = inicio.replace(month=inicio.month + 1)
    return inicio, proximo - dt.timedelta(days=1)
