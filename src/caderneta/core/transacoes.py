"""Lancamentos: gravar, consultar o ultimo, desfazer.

Parte do nucleo de regras: nao sabe que o Telegram existe.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import ENTRADA, GASTO, Transacao


class ValorInvalidoError(ValueError):
    pass


def registrar_transacao(
    sessao: Session,
    *,
    tipo: str,
    valor_centavos: int,
    data: dt.date,
    categoria_id: int | None = None,
    descricao: str | None = None,
    origem_update_id: int | None = None,
) -> tuple[Transacao, bool]:
    """Grava um lancamento.

    Devolve (transacao, criada). `criada=False` significa que este update_id ja
    tinha sido processado - update reenviado pelo Telegram, nao um lancamento novo.
    """
    if tipo not in (GASTO, ENTRADA):
        raise ValueError(f"tipo invalido: {tipo!r}")
    if valor_centavos <= 0:
        raise ValorInvalidoError("valor precisa ser positivo")

    if origem_update_id is not None:
        ja = sessao.scalar(
            select(Transacao).where(Transacao.origem_update_id == origem_update_id)
        )
        if ja is not None:
            return ja, False

    transacao = Transacao(
        tipo=tipo,
        valor_centavos=valor_centavos,
        data=data,
        categoria_id=categoria_id,
        descricao=(descricao or "").strip() or None,
        origem_update_id=origem_update_id,
    )
    sessao.add(transacao)
    try:
        sessao.flush()
    except IntegrityError:
        # Corrida: outro processamento do mesmo update chegou primeiro.
        sessao.rollback()
        ja = sessao.scalar(
            select(Transacao).where(Transacao.origem_update_id == origem_update_id)
        )
        if ja is None:
            raise
        return ja, False

    return transacao, True


def ultima_transacao(sessao: Session) -> Transacao | None:
    return sessao.scalar(select(Transacao).order_by(Transacao.id.desc()).limit(1))


@dataclass(frozen=True)
class TransacaoRemovida:
    id: int
    tipo: str
    valor_centavos: int
    data: dt.date
    categoria: str | None
    descricao: str | None


def desfazer_ultima(sessao: Session) -> TransacaoRemovida | None:
    """Remove o ultimo lancamento e devolve uma copia do que foi removido."""
    alvo = ultima_transacao(sessao)
    if alvo is None:
        return None
    copia = TransacaoRemovida(
        id=alvo.id,
        tipo=alvo.tipo,
        valor_centavos=alvo.valor_centavos,
        data=alvo.data,
        categoria=alvo.categoria.nome if alvo.categoria else None,
        descricao=alvo.descricao,
    )
    sessao.delete(alvo)
    sessao.flush()
    return copia


def remover_transacao(sessao: Session, transacao_id: int) -> bool:
    alvo = sessao.get(Transacao, transacao_id)
    if alvo is None:
        return False
    sessao.delete(alvo)
    sessao.flush()
    return True
