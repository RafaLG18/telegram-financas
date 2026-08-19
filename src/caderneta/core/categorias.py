"""Categorias: catalogo padrao e busca tolerante.

Parte do nucleo de regras: nao sabe que o Telegram existe.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AMBOS, ENTRADA, GASTO, Categoria

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
