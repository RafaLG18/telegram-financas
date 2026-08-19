"""Consultas e correcao: /hoje, /mes, /extrato, /desfazer."""

from __future__ import annotations

import datetime as dt
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from ..config import Config
from ..core import desfazer_ultima, intervalo_do_mes, remover_transacao, resumo
from ..db import session_scope
from ..keyboards import CB_DESFAZER
from ..models import Transacao
from ..textos import linha_transacao, render_resumo, transacao_removida

log = logging.getLogger(__name__)
router = Router(name="relatorios")

_MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


@router.message(Command("hoje"))
async def cmd_hoje(message: Message, config: Config) -> None:
    hoje = dt.datetime.now(config.tz).date()
    with session_scope() as sessao:
        r = resumo(sessao, hoje, hoje)
    await message.answer(render_resumo(r, f"Hoje · {hoje.strftime('%d/%m')}"))


@router.message(Command("mes", "mês"))
async def cmd_mes(message: Message, config: Config) -> None:
    hoje = dt.datetime.now(config.tz).date()
    inicio, fim = intervalo_do_mes(hoje)
    with session_scope() as sessao:
        r = resumo(sessao, inicio, fim)
    titulo = f"{_MESES[hoje.month - 1].capitalize()} de {hoje.year}"
    await message.answer(render_resumo(r, titulo))


@router.message(Command("extrato"))
async def cmd_extrato(message: Message, config: Config) -> None:
    hoje = dt.datetime.now(config.tz).date()
    with session_scope() as sessao:
        transacoes = list(
            sessao.scalars(
                select(Transacao).order_by(Transacao.id.desc()).limit(15)
            ).all()
        )
        linhas = [
            linha_transacao(
                t.tipo,
                t.valor_centavos,
                t.data,
                t.categoria.nome if t.categoria else None,
                t.descricao,
                hoje,
            )
            for t in transacoes
        ]

    if not linhas:
        await message.answer("Nenhum lançamento ainda.")
        return

    await message.answer("<b>Últimos lançamentos</b>\n\n" + "\n\n".join(linhas))


@router.message(Command("desfazer"))
async def cmd_desfazer(message: Message, config: Config) -> None:
    hoje = dt.datetime.now(config.tz).date()
    with session_scope() as sessao:
        removida = desfazer_ultima(sessao)
        texto = (
            transacao_removida(removida, hoje)
            if removida is not None
            else "Não há lançamento para desfazer."
        )
    await message.answer(texto)


@router.callback_query(F.data.startswith(f"{CB_DESFAZER}:"))
async def clicou_desfazer(callback: CallbackQuery) -> None:
    transacao_id = int((callback.data or "").split(":")[1])

    with session_scope() as sessao:
        removeu = remover_transacao(sessao, transacao_id)

    await callback.answer("Desfeito" if removeu else "Esse lançamento já não existe")
    try:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "Lançamento desfeito." if removeu else "Esse lançamento já foi removido.",
            reply_markup=None,
        )
    except (TelegramBadRequest, AttributeError):
        log.debug("falha ao editar mensagem do desfazer", exc_info=True)
