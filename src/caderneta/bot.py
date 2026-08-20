"""Entry point: starts polling, the health server and registers the handlers."""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from .config import Config, ConfigError, load_config
from .core import purge_old_drafts, seed_categories
from .db import init_engine, session_scope
from .handlers import build_router
from .health import HealthState, start_health_server
from .middlewares import OwnerOnly

log = logging.getLogger("caderneta")

# Command names and descriptions are what the user sees in Telegram: pt-BR.
COMMANDS = [
    BotCommand(command="registrar", description="Registrar gasto ou entrada"),
    BotCommand(command="hoje", description="Resumo de hoje"),
    BotCommand(command="mes", description="Resumo do mês"),
    BotCommand(command="extrato", description="Últimos lançamentos"),
    BotCommand(command="desfazer", description="Remover o último lançamento"),
    BotCommand(command="categorias", description="Listar categorias"),
    BotCommand(command="cancelar", description="Descartar registro em andamento"),
    BotCommand(command="ajuda", description="Como usar"),
]


def prepare_database(config: Config) -> None:
    init_engine(config.database_url)
    with session_scope() as session:
        new = seed_categories(session)
        old = purge_old_drafts(session)
    if new:
        log.info("categories created: %s", new)
    if old:
        log.info("abandoned drafts removed: %s", old)


async def run(config: Config) -> None:
    prepare_database(config)

    state = HealthState()
    runner = await start_health_server(config.health_port, state)

    api_session = None
    if config.telegram_api_url:
        log.info("using alternative Bot API: %s", config.telegram_api_url)
        api_session = AiohttpSession(
            api=TelegramAPIServer.from_base(config.telegram_api_url)
        )

    bot = Bot(
        token=config.bot_token,
        session=api_session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp["config"] = config
    dp.update.outer_middleware(OwnerOnly(config.owner_chat_id))
    dp.include_router(build_router())

    try:
        me = await bot.get_me()
        log.info("connected as @%s", me.username)
        await bot.set_my_commands(COMMANDS)
        state.ready = True
        # No drop_pending_updates: the UNIQUE on source_update_id already guards
        # against reprocessing, and this way nothing you sent gets lost.
        await dp.start_polling(bot, handle_signals=True)
    finally:
        state.ready = False
        await runner.cleanup()
        await bot.session.close()


def main() -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
        log.error("%s", exc)
        return 2

    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    if config.owner_chat_id is None:
        log.warning(
            "OWNER_CHAT_ID empty - bootstrap mode. The bot will only tell you "
            "your chat_id and will not process commands."
        )

    try:
        asyncio.run(run(config))
    except (KeyboardInterrupt, SystemExit):
        log.info("shutting down")
    return 0


if __name__ == "__main__":
    sys.exit(main())
