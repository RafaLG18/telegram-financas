"""Atalho de texto livre: '50 mercado' vira lancamento direto.

Fica por ultimo na cadeia de routers: so recebe o que ninguem mais quis.
"""

from __future__ import annotations

import datetime as dt
import logging

from aiogram import F, Router
from aiogram.types import Message

from ..config import Config
from ..core import achar_categoria_por_nome, registrar_transacao
from ..db import session_scope
from ..keyboards import teclado_desfazer
from ..models import ENTRADA, GASTO
from ..parse import parse_lancamento
from ..textos import transacao_registrada

log = logging.getLogger(__name__)
router = Router(name="rapido")

_PALAVRAS_ENTRADA = ("recebi", "salario", "salário", "entrada", "rendimento")

_NAO_ENTENDI = (
    "Não entendi.\n\n"
    "Mande algo como <code>50 mercado</code> ou <code>1.250,00 aluguel ontem</code>.\n"
    "Para entrada, comece com <code>+</code>: <code>+3000 salário</code>.\n\n"
    "Ou use /registrar para o passo a passo."
)


def _detecta_tipo(texto: str) -> tuple[str, str]:
    """Devolve (tipo, texto_sem_marcador)."""
    limpo = texto.strip()
    if limpo.startswith("+"):
        return ENTRADA, limpo[1:].strip()
    if limpo.startswith("-"):
        return GASTO, limpo[1:].strip()
    if any(p in limpo.lower() for p in _PALAVRAS_ENTRADA):
        return ENTRADA, limpo
    return GASTO, limpo


@router.message(F.text & ~F.text.startswith("/"))
async def texto_livre(message: Message, config: Config, update_id: int) -> None:
    hoje = dt.datetime.now(config.tz).date()
    tipo, texto = _detecta_tipo(message.text or "")

    lancamento = parse_lancamento(texto, hoje)
    if lancamento is None:
        await message.answer(_NAO_ENTENDI)
        return

    with session_scope() as sessao:
        categoria = achar_categoria_por_nome(sessao, lancamento.descricao)
        if categoria is None and lancamento.descricao:
            primeira_palavra = lancamento.descricao.split()[0]
            categoria = achar_categoria_por_nome(sessao, primeira_palavra)

        transacao, criada = registrar_transacao(
            sessao,
            tipo=tipo,
            valor_centavos=lancamento.valor_centavos,
            data=lancamento.data,
            categoria_id=categoria.id if categoria else None,
            descricao=lancamento.descricao or None,
            origem_update_id=update_id,
        )
        texto_resposta = transacao_registrada(transacao, hoje)
        transacao_id = transacao.id

    if not criada:
        # Update reenviado pelo Telegram: nao duplicamos nem confundimos o usuario.
        log.info("update %s ja processado, ignorando reenvio", update_id)
        return

    await message.answer(texto_resposta, reply_markup=teclado_desfazer(transacao_id))
