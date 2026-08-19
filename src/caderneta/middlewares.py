"""Autorizacao.

Bot do Telegram e publico por padrao: qualquer um que descubra o @ conversa com
ele. Este middleware e a unica coisa entre suas financas e um estranho.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

log = logging.getLogger(__name__)


def _chat_id_do_update(update: Update) -> int | None:
    for evento in (update.message, update.edited_message, update.channel_post):
        if evento is not None:
            return evento.chat.id
    if update.callback_query is not None and update.callback_query.message is not None:
        return update.callback_query.message.chat.id
    if update.callback_query is not None:
        return update.callback_query.from_user.id
    return None


class SomenteDono(BaseMiddleware):
    def __init__(self, owner_chat_id: int | None) -> None:
        self.owner_chat_id = owner_chat_id

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Update):
            return await handler(event, data)

        chat_id = _chat_id_do_update(event)

        # Modo bootstrap: sem OWNER_CHAT_ID configurado, o bot so ajuda voce a
        # descobrir o seu id. Nao processa nenhum comando.
        if self.owner_chat_id is None:
            log.warning("OWNER_CHAT_ID nao configurado. chat_id recebido: %s", chat_id)
            if event.message is not None:
                await event.message.answer(
                    "Bot ainda nao configurado.\n"
                    f"Seu chat_id e <code>{chat_id}</code> — "
                    "coloque em OWNER_CHAT_ID e reinicie."
                )
            return None

        if chat_id != self.owner_chat_id:
            log.warning("acesso negado para chat_id=%s", chat_id)
            return None

        data["update_id"] = event.update_id
        return await handler(event, data)
