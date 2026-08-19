"""Regras de negocio.

Este pacote NAO sabe que o Telegram existe. E a fronteira que permite testar
tudo sem subir bot e, mais pra frente, plugar outra interface (web, CLI, export).

Dividido por dominio: `categorias`, `transacoes`, `relatorios` e `rascunhos`.
A API publica e re-exportada aqui, entao `from ..core import resumo` continua
valendo — importar do modulo especifico e opcional, nao obrigatorio.
"""

from __future__ import annotations

from .categorias import (
    CATEGORIAS_PADRAO,
    achar_categoria_por_nome,
    listar_categorias,
    seed_categorias,
)
from .rascunhos import (
    concluir_rascunho,
    descartar_rascunho,
    limpar_rascunhos_do_chat,
    limpar_rascunhos_velhos,
    novo_rascunho,
    pegar_rascunho,
    rascunho_ativo,
)
from .relatorios import LinhaCategoria, Resumo, intervalo_do_mes, resumo
from .transacoes import (
    TransacaoRemovida,
    ValorInvalidoError,
    desfazer_ultima,
    registrar_transacao,
    remover_transacao,
    ultima_transacao,
)

__all__ = [
    "CATEGORIAS_PADRAO",
    "LinhaCategoria",
    "Resumo",
    "TransacaoRemovida",
    "ValorInvalidoError",
    "achar_categoria_por_nome",
    "concluir_rascunho",
    "descartar_rascunho",
    "desfazer_ultima",
    "intervalo_do_mes",
    "limpar_rascunhos_do_chat",
    "limpar_rascunhos_velhos",
    "listar_categorias",
    "novo_rascunho",
    "pegar_rascunho",
    "rascunho_ativo",
    "registrar_transacao",
    "remover_transacao",
    "resumo",
    "seed_categorias",
    "ultima_transacao",
]
