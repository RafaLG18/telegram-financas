"""Regras de negocio.

Este modulo NAO sabe que o Telegram existe. E a fronteira que permite testar
tudo sem subir bot e, mais pra frente, plugar outra interface (web, CLI, export).
"""

from __future__ import annotations

import datetime as dt
import secrets
from dataclasses import dataclass, field

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import (
    AMBOS,
    ENTRADA,
    GASTO,
    Categoria,
    Rascunho,
    Transacao,
)

CATEGORIAS_PADRAO: tuple[tuple[str, str], ...] = (
    ("Mercado", GASTO),
    ("Transporte", GASTO),
    ("Casa", GASTO),
    ("Alimentação", GASTO),
    ("Saúde", GASTO),
    ("Lazer", GASTO),
    ("Salário", ENTRADA),
    ("Outras entradas", ENTRADA),
    ("Outros", AMBOS),
)


# --------------------------------------------------------------------------
# Categorias
# --------------------------------------------------------------------------


def seed_categorias(sessao: Session) -> int:
    """Insere as categorias padrao que ainda nao existem. Idempotente."""
    existentes = set(sessao.scalars(select(Categoria.nome)).all())
    novas = [
        Categoria(nome=nome, tipo=tipo)
        for nome, tipo in CATEGORIAS_PADRAO
        if nome not in existentes
    ]
    sessao.add_all(novas)
    sessao.flush()
    return len(novas)


def listar_categorias(sessao: Session, tipo: str | None = None) -> list[Categoria]:
    stmt = select(Categoria).where(Categoria.ativa.is_(True))
    if tipo is not None:
        stmt = stmt.where(Categoria.tipo.in_((tipo, AMBOS)))
    return list(sessao.scalars(stmt.order_by(Categoria.nome)).all())


def achar_categoria_por_nome(sessao: Session, texto: str) -> Categoria | None:
    """Casamento tolerante: ignora caixa e aceita prefixo ('merc' -> Mercado)."""
    alvo = texto.strip().lower()
    if not alvo:
        return None
    candidatas = listar_categorias(sessao)
    for cat in candidatas:
        if cat.nome.lower() == alvo:
            return cat
    prefixos = [c for c in candidatas if c.nome.lower().startswith(alvo)]
    return prefixos[0] if len(prefixos) == 1 else None


# --------------------------------------------------------------------------
# Transacoes
# --------------------------------------------------------------------------


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


# --------------------------------------------------------------------------
# Relatorios
# --------------------------------------------------------------------------


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


# --------------------------------------------------------------------------
# Rascunhos (estado do fluxo guiado)
# --------------------------------------------------------------------------


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
