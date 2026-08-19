"""Rascunho: o lancamento em construcao pelo fluxo guiado.

Mora no banco, nao em memoria — sobrevive a restart e o id curto e o que viaja
no callback_data dos botoes.
"""

from __future__ import annotations

import datetime as dt
import secrets

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import Rascunho, Transacao
from .transacoes import registrar_transacao


def novo_rascunho(sessao: Session, *, chat_id: int, estado: str) -> Rascunho:
    rascunho = Rascunho(id=secrets.token_hex(4), chat_id=chat_id, estado=estado)
    sessao.add(rascunho)
    sessao.flush()
    return rascunho


def pegar_rascunho(sessao: Session, rascunho_id: str) -> Rascunho | None:
    return sessao.get(Rascunho, rascunho_id)


def rascunho_ativo(sessao: Session, chat_id: int) -> Rascunho | None:
    return sessao.scalar(
        select(Rascunho)
        .where(Rascunho.chat_id == chat_id)
        .order_by(Rascunho.criado_em.desc())
        .limit(1)
    )


def descartar_rascunho(sessao: Session, rascunho_id: str) -> None:
    sessao.execute(delete(Rascunho).where(Rascunho.id == rascunho_id))


def limpar_rascunhos_do_chat(sessao: Session, chat_id: int) -> int:
    resultado = sessao.execute(delete(Rascunho).where(Rascunho.chat_id == chat_id))
    return resultado.rowcount or 0


def limpar_rascunhos_velhos(sessao: Session, horas: int = 24) -> int:
    limite = dt.datetime.utcnow() - dt.timedelta(hours=horas)
    resultado = sessao.execute(delete(Rascunho).where(Rascunho.criado_em < limite))
    return resultado.rowcount or 0


def concluir_rascunho(
    sessao: Session, rascunho: Rascunho, *, origem_update_id: int | None = None
) -> Transacao:
    """Converte um rascunho completo em transacao e descarta o rascunho."""
    if rascunho.tipo is None or rascunho.valor_centavos is None:
        raise ValueError("rascunho incompleto")

    transacao, _ = registrar_transacao(
        sessao,
        tipo=rascunho.tipo,
        valor_centavos=rascunho.valor_centavos,
        data=rascunho.data or dt.date.today(),
        categoria_id=rascunho.categoria_id,
        descricao=rascunho.descricao,
        origem_update_id=origem_update_id,
    )
    descartar_rascunho(sessao, rascunho.id)
    return transacao
