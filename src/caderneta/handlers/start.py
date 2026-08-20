from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from ..core import list_categories
from ..db import session_scope
from ..models import BOTH, INCOME
from ..texts import HELP

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(HELP)


@router.message(Command("ajuda", "help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP)


@router.message(Command("categorias"))
async def cmd_categories(message: Message) -> None:
    with session_scope() as session:
        categories = list_categories(session)

    if not categories:
        await message.answer("Nenhuma categoria cadastrada.")
        return

    lines = ["<b>Categorias</b>", ""]
    for cat in categories:
        mark = "🟢" if cat.kind == INCOME else ("⚪" if cat.kind == BOTH else "🔴")
        lines.append(f"{mark} {cat.name}")
    await message.answer("\n".join(lines))
