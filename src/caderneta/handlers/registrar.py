"""Fluxo guiado: /registrar -> tipo -> valor -> categoria -> confirmacao."""

from __future__ import annotations

import datetime as dt
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, Filter
from aiogram.types import CallbackQuery, Message
from sqlalchemy.orm import Session

from ..config import Config
from ..core import (
    concluir_rascunho,
    descartar_rascunho,
    limpar_rascunhos_do_chat,
    listar_categorias,
    novo_rascunho,
    pegar_rascunho,
    rascunho_ativo,
)
from ..db import session_scope
from ..keyboards import (
    CB_CANCELA,
    CB_CATEGORIA,
    CB_CONFIRMA,
    CB_DATA,
    CB_DATA_LIVRE,
    CB_MUDAR_DATA,
    CB_TIPO,
    teclado_categorias,
    teclado_confirmacao,
    teclado_datas,
    teclado_tipo,
)
from ..models import (
    Rascunho,
    E_CATEGORIA,
    E_CONFIRMACAO,
    E_DATA_LIVRE,
    E_TIPO,
    E_VALOR,
)
from ..parse import DATA_FUTURA, parse_data_estrita, parse_valor
from ..textos import previa_rascunho, transacao_registrada

log = logging.getLogger(__name__)
router = Router(name="registrar")

_EXPIRADO = "Esse lançamento já foi finalizado ou cancelado. Mande /registrar de novo."
_PERGUNTA_DATA = (
    "Qual a data? Ex: <code>15/08</code>, <code>15/08/2025</code> ou "
    "<code>ontem</code>.\n\nOu /cancelar."
)


async def _limpar_teclado(callback: CallbackQuery, texto: str) -> None:
    """Edita a mensagem removendo os botoes — mata o 'botao zumbi'."""
    try:
        await callback.message.edit_text(texto, reply_markup=None)  # type: ignore[union-attr]
    except (TelegramBadRequest, AttributeError):
        log.debug("nao consegui editar a mensagem do callback", exc_info=True)


def _rid(callback: CallbackQuery) -> str:
    return (callback.data or "").split(":")[1]


def _previa(sessao: Session, rascunho: Rascunho, hoje: dt.date) -> str:
    nome = next(
        (c.nome for c in listar_categorias(sessao) if c.id == rascunho.categoria_id),
        None,
    )
    return previa_rascunho(rascunho, nome, hoje)


class _AguardandoTexto(Filter):
    """Casa qualquer texto enquanto o rascunho ativo estiver no estado esperado."""

    estado: str

    async def __call__(self, message: Message) -> bool | dict:
        if not message.text or message.text.startswith("/"):
            return False
        with session_scope() as sessao:
            rascunho = rascunho_ativo(sessao, message.chat.id)
            if rascunho is not None and rascunho.estado == self.estado:
                return {"rascunho_id": rascunho.id}
        return False


class AguardandoValor(_AguardandoTexto):
    estado = E_VALOR


class AguardandoData(_AguardandoTexto):
    estado = E_DATA_LIVRE


@router.message(Command("registrar", "novo"))
async def cmd_registrar(message: Message) -> None:
    with session_scope() as sessao:
        limpar_rascunhos_do_chat(sessao, message.chat.id)
        rascunho = novo_rascunho(sessao, chat_id=message.chat.id, estado=E_TIPO)
        rascunho_id = rascunho.id

    enviada = await message.answer(
        "O que você quer registrar?", reply_markup=teclado_tipo(rascunho_id)
    )

    with session_scope() as sessao:
        rascunho = pegar_rascunho(sessao, rascunho_id)
        if rascunho is not None:
            rascunho.message_id = enviada.message_id


@router.message(Command("cancelar"))
async def cmd_cancelar(message: Message) -> None:
    with session_scope() as sessao:
        removidos = limpar_rascunhos_do_chat(sessao, message.chat.id)
    await message.answer(
        "Registro em andamento descartado." if removidos else "Nada em andamento."
    )


@router.callback_query(F.data.startswith(f"{CB_TIPO}:"))
async def escolheu_tipo(callback: CallbackQuery) -> None:
    await callback.answer()
    rascunho_id = _rid(callback)
    tipo = (callback.data or "").split(":")[2]

    with session_scope() as sessao:
        rascunho = pegar_rascunho(sessao, rascunho_id)
        if rascunho is None:
            await _limpar_teclado(callback, _EXPIRADO)
            return
        rascunho.tipo = tipo
        rascunho.estado = E_VALOR

    rotulo = "gasto" if tipo == "gasto" else "entrada"
    await _limpar_teclado(
        callback,
        f"Qual o valor do {rotulo}?\n\n"
        "<i>Pode mandar só o número (50) ou já com a descrição "
        "(50 pão na padaria).</i>",
    )


@router.message(AguardandoValor())
async def recebeu_valor(message: Message, rascunho_id: str, config: Config) -> None:
    texto = (message.text or "").strip()
    partes = texto.split(maxsplit=1)
    valor = parse_valor(partes[0]) if partes else None

    if valor is None:
        await message.answer(
            "Não entendi esse valor. Tente <code>50</code>, <code>50,90</code> "
            "ou <code>1.250,00</code>.\n\nOu /cancelar."
        )
        return

    descricao = partes[1] if len(partes) > 1 else None

    with session_scope() as sessao:
        rascunho = pegar_rascunho(sessao, rascunho_id)
        if rascunho is None:
            await message.answer(_EXPIRADO)
            return
        rascunho.valor_centavos = valor
        rascunho.descricao = descricao
        rascunho.estado = E_CATEGORIA
        rascunho.data = dt.datetime.now(config.tz).date()
        categorias = listar_categorias(sessao, tipo=rascunho.tipo)

    await message.answer(
        "Qual categoria?", reply_markup=teclado_categorias(rascunho_id, categorias)
    )


@router.callback_query(F.data.startswith(f"{CB_CATEGORIA}:"))
async def escolheu_categoria(callback: CallbackQuery, config: Config) -> None:
    await callback.answer()
    rascunho_id = _rid(callback)
    categoria_id = int((callback.data or "").split(":")[2])
    hoje = dt.datetime.now(config.tz).date()

    with session_scope() as sessao:
        rascunho = pegar_rascunho(sessao, rascunho_id)
        if rascunho is None:
            await _limpar_teclado(callback, _EXPIRADO)
            return
        rascunho.categoria_id = categoria_id
        rascunho.estado = E_CONFIRMACAO
        texto = _previa(sessao, rascunho, hoje)

    try:
        await callback.message.edit_text(  # type: ignore[union-attr]
            texto, reply_markup=teclado_confirmacao(rascunho_id)
        )
    except (TelegramBadRequest, AttributeError):
        log.debug("falha ao editar previa", exc_info=True)


@router.callback_query(F.data.startswith(f"{CB_MUDAR_DATA}:"))
async def pediu_mudar_data(callback: CallbackQuery) -> None:
    await callback.answer()
    rascunho_id = _rid(callback)

    with session_scope() as sessao:
        if pegar_rascunho(sessao, rascunho_id) is None:
            await _limpar_teclado(callback, _EXPIRADO)
            return

    try:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "Quando foi?", reply_markup=teclado_datas(rascunho_id)
        )
    except (TelegramBadRequest, AttributeError):
        log.debug("falha ao editar seletor de data", exc_info=True)


@router.callback_query(F.data.startswith(f"{CB_DATA}:"))
async def escolheu_data(callback: CallbackQuery, config: Config) -> None:
    await callback.answer()
    rascunho_id = _rid(callback)
    dias = int((callback.data or "").split(":")[2])
    hoje = dt.datetime.now(config.tz).date()

    with session_scope() as sessao:
        rascunho = pegar_rascunho(sessao, rascunho_id)
        if rascunho is None:
            await _limpar_teclado(callback, _EXPIRADO)
            return
        rascunho.data = hoje - dt.timedelta(days=dias)
        rascunho.estado = E_CONFIRMACAO
        texto = _previa(sessao, rascunho, hoje)

    try:
        await callback.message.edit_text(  # type: ignore[union-attr]
            texto, reply_markup=teclado_confirmacao(rascunho_id)
        )
    except (TelegramBadRequest, AttributeError):
        log.debug("falha ao voltar pra previa", exc_info=True)


@router.callback_query(F.data.startswith(f"{CB_DATA_LIVRE}:"))
async def pediu_data_livre(callback: CallbackQuery) -> None:
    await callback.answer()
    rascunho_id = _rid(callback)

    with session_scope() as sessao:
        rascunho = pegar_rascunho(sessao, rascunho_id)
        if rascunho is None:
            await _limpar_teclado(callback, _EXPIRADO)
            return
        rascunho.estado = E_DATA_LIVRE

    await _limpar_teclado(callback, _PERGUNTA_DATA)


@router.message(AguardandoData())
async def recebeu_data(message: Message, rascunho_id: str, config: Config) -> None:
    hoje = dt.datetime.now(config.tz).date()
    lida = parse_data_estrita(message.text or "", hoje)

    if lida.data is None:
        # Sem mexer no rascunho: o valor e a categoria ja digitados continuam
        # vivos e o proximo texto cai aqui de novo.
        await message.answer(
            "Essa data ainda não aconteceu. Lançamento é fato ocorrido — "
            "manda uma data de hoje ou de antes.\n\nOu /cancelar."
            if lida.motivo == DATA_FUTURA
            else f"Não entendi essa data.\n\n{_PERGUNTA_DATA}"
        )
        return

    with session_scope() as sessao:
        rascunho = pegar_rascunho(sessao, rascunho_id)
        if rascunho is None:
            await message.answer(_EXPIRADO)
            return
        rascunho.data = lida.data
        rascunho.estado = E_CONFIRMACAO
        texto = _previa(sessao, rascunho, hoje)

    await message.answer(texto, reply_markup=teclado_confirmacao(rascunho_id))


@router.callback_query(F.data.startswith(f"{CB_CONFIRMA}:"))
async def confirmou(callback: CallbackQuery, config: Config) -> None:
    await callback.answer("Registrando…")
    rascunho_id = _rid(callback)
    hoje = dt.datetime.now(config.tz).date()

    with session_scope() as sessao:
        rascunho = pegar_rascunho(sessao, rascunho_id)
        if rascunho is None:
            # Clique duplo ou botao antigo: o primeiro clique ja gravou.
            await _limpar_teclado(callback, _EXPIRADO)
            return
        transacao = concluir_rascunho(sessao, rascunho)
        texto = transacao_registrada(transacao, hoje)

    await _limpar_teclado(callback, texto)


@router.callback_query(F.data.startswith(f"{CB_CANCELA}:"))
async def cancelou(callback: CallbackQuery) -> None:
    await callback.answer("Cancelado")
    rascunho_id = _rid(callback)
    with session_scope() as sessao:
        descartar_rascunho(sessao, rascunho_id)
    await _limpar_teclado(callback, "Cancelado, nada foi registrado.")
