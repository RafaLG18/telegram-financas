"""Modelo de dados.

Decisoes que valem lembrar:
- valor sempre POSITIVO em centavos; o sinal vem de `tipo`.
- `data` e a data do fato (fuso local); `criado_em` e o instante do registro (UTC).
- `origem_update_id` e UNIQUE: e a defesa contra update reenviado pelo Telegram.
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

GASTO = "gasto"
ENTRADA = "entrada"
AMBOS = "ambos"


class Base(DeclarativeBase):
    pass


class Categoria(Base):
    __tablename__ = "categoria"
    __table_args__ = (
        CheckConstraint("tipo IN ('gasto','entrada','ambos')", name="ck_categoria_tipo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(40), unique=True)
    tipo: Mapped[str] = mapped_column(String(10))
    ativa: Mapped[bool] = mapped_column(default=True)

    def aceita(self, tipo: str) -> bool:
        return self.tipo == AMBOS or self.tipo == tipo


class Transacao(Base):
    __tablename__ = "transacao"
    __table_args__ = (
        CheckConstraint("tipo IN ('gasto','entrada')", name="ck_transacao_tipo"),
        CheckConstraint("valor_centavos > 0", name="ck_transacao_valor_positivo"),
        Index("idx_transacao_data", "data"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(10))
    valor_centavos: Mapped[int] = mapped_column(Integer)
    data: Mapped[dt.date] = mapped_column(Date)
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("categoria.id"))
    # Reservado para a v2 (carteira, Nubank, ...). Nao usado ainda.
    conta_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    descricao: Mapped[str | None] = mapped_column(String(200), nullable=True)
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    origem_update_id: Mapped[int | None] = mapped_column(
        Integer, unique=True, nullable=True
    )

    categoria: Mapped[Categoria | None] = relationship(lazy="joined")


class Rascunho(Base):
    """Lancamento em construcao pelo fluxo guiado.

    Mora no banco (e nao em memoria) por dois motivos: sobrevive a restart e o
    `id` curto e o que viaja no callback_data dos botoes, resolvendo o problema
    do botao clicado dias depois.
    """

    __tablename__ = "rascunho"

    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    estado: Mapped[str] = mapped_column(String(20))
    chat_id: Mapped[int] = mapped_column(Integer)
    message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    tipo: Mapped[str | None] = mapped_column(String(10), nullable=True)
    valor_centavos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    categoria_id: Mapped[int | None] = mapped_column(
        ForeignKey("categoria.id"), nullable=True
    )
    descricao: Mapped[str | None] = mapped_column(String(200), nullable=True)

    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )


# Estados do fluxo guiado.
E_TIPO = "tipo"
E_VALOR = "valor"
E_CATEGORIA = "categoria"
E_CONFIRMACAO = "confirmacao"
