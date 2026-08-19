"""Teclados inline.

O callback_data do Telegram tem limite duro de 64 bytes, entao ele carrega
apenas ponteiros curtos ("acao:rascunho:valor"). O dado real vive no banco.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .models import Categoria, ENTRADA, GASTO

CB_TIPO = "tipo"
CB_CATEGORIA = "cat"
CB_DATA = "data"
CB_CONFIRMA = "ok"
CB_CANCELA = "no"
CB_MUDAR_DATA = "dt?"
CB_DESFAZER = "undo"


def teclado_tipo(rascunho_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔴 Gasto", callback_data=f"{CB_TIPO}:{rascunho_id}:{GASTO}")
    b.button(text="🟢 Entrada", callback_data=f"{CB_TIPO}:{rascunho_id}:{ENTRADA}")
    b.button(text="✖️ Cancelar", callback_data=f"{CB_CANCELA}:{rascunho_id}")
    b.adjust(2, 1)
    return b.as_markup()


def teclado_categorias(
    rascunho_id: str, categorias: list[Categoria]
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for cat in categorias:
        b.button(text=cat.nome, callback_data=f"{CB_CATEGORIA}:{rascunho_id}:{cat.id}")
    b.button(text="✖️ Cancelar", callback_data=f"{CB_CANCELA}:{rascunho_id}")
    b.adjust(2)
    return b.as_markup()


def teclado_confirmacao(rascunho_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Confirmar", callback_data=f"{CB_CONFIRMA}:{rascunho_id}")
    b.button(text="📅 Mudar data", callback_data=f"{CB_MUDAR_DATA}:{rascunho_id}")
    b.button(text="✖️ Cancelar", callback_data=f"{CB_CANCELA}:{rascunho_id}")
    b.adjust(1, 2)
    return b.as_markup()


def teclado_datas(rascunho_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for rotulo, dias in (("Hoje", 0), ("Ontem", 1), ("Anteontem", 2)):
        b.button(text=rotulo, callback_data=f"{CB_DATA}:{rascunho_id}:{dias}")
    b.button(text="✖️ Cancelar", callback_data=f"{CB_CANCELA}:{rascunho_id}")
    b.adjust(3, 1)
    return b.as_markup()


def teclado_desfazer(transacao_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="↩️ Desfazer", callback_data=f"{CB_DESFAZER}:{transacao_id}")
    return b.as_markup()
