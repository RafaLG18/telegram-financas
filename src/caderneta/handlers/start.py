from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from ..core import listar_categorias
from ..db import session_scope
from ..models import AMBOS, ENTRADA
from ..textos import AJUDA

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(AJUDA)


@router.message(Command("ajuda", "help"))
async def cmd_ajuda(message: Message) -> None:
    await message.answer(AJUDA)


@router.message(Command("categorias"))
async def cmd_categorias(message: Message) -> None:
    with session_scope() as sessao:
        categorias = listar_categorias(sessao)

    if not categorias:
        await message.answer("Nenhuma categoria cadastrada.")
        return

    linhas = ["<b>Categorias</b>", ""]
    for cat in categorias:
        marca = "🟢" if cat.tipo == ENTRADA else ("⚪" if cat.tipo == AMBOS else "🔴")
        linhas.append(f"{marca} {cat.nome}")
    await message.answer("\n".join(linhas))
