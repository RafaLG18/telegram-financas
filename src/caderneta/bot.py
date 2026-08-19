"""Ponto de entrada: sobe o polling, o health server e registra os handlers."""

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
from .core import limpar_rascunhos_velhos, seed_categorias
from .db import init_engine, session_scope
from .handlers import montar_router
from .health import EstadoSaude, iniciar_servidor_health
from .middlewares import SomenteDono

log = logging.getLogger("caderneta")

COMANDOS = [
    BotCommand(command="registrar", description="Registrar gasto ou entrada"),
    BotCommand(command="hoje", description="Resumo de hoje"),
    BotCommand(command="mes", description="Resumo do mês"),
    BotCommand(command="extrato", description="Últimos lançamentos"),
    BotCommand(command="desfazer", description="Remover o último lançamento"),
    BotCommand(command="categorias", description="Listar categorias"),
    BotCommand(command="cancelar", description="Descartar registro em andamento"),
    BotCommand(command="ajuda", description="Como usar"),
]


def preparar_banco(config: Config) -> None:
    init_engine(config.database_url)
    with session_scope() as sessao:
        novas = seed_categorias(sessao)
        velhos = limpar_rascunhos_velhos(sessao)
    if novas:
        log.info("categorias criadas: %s", novas)
    if velhos:
        log.info("rascunhos abandonados removidos: %s", velhos)


async def executar(config: Config) -> None:
    preparar_banco(config)

    estado = EstadoSaude()
    runner = await iniciar_servidor_health(config.health_port, estado)

    sessao_api = None
    if config.telegram_api_url:
        log.info("usando Bot API alternativa: %s", config.telegram_api_url)
        sessao_api = AiohttpSession(
            api=TelegramAPIServer.from_base(config.telegram_api_url)
        )

    bot = Bot(
        token=config.bot_token,
        session=sessao_api,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp["config"] = config
    dp.update.outer_middleware(SomenteDono(config.owner_chat_id))
    dp.include_router(montar_router())

    try:
        eu = await bot.get_me()
        log.info("conectado como @%s", eu.username)
        await bot.set_my_commands(COMANDOS)
        estado.pronto = True
        # Sem drop_pending_updates: o UNIQUE de origem_update_id ja protege
        # contra reprocessamento, e assim nada que voce mandou se perde.
        await dp.start_polling(bot, handle_signals=True)
    finally:
        estado.pronto = False
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
            "OWNER_CHAT_ID vazio — modo bootstrap. O bot so vai te informar o "
            "seu chat_id e nao processa comandos."
        )

    try:
        asyncio.run(executar(config))
    except (KeyboardInterrupt, SystemExit):
        log.info("encerrando")
    return 0


if __name__ == "__main__":
    sys.exit(main())
