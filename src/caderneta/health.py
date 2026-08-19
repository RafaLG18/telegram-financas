"""Endpoint de health.

Um bot em polling nao abre porta nenhuma, o que deixaria as probes do Kubernetes
sem nada pra medir. O aiohttp ja vem junto com o aiogram, entao isto sai de graca.
"""

from __future__ import annotations

import logging

from aiohttp import web
from sqlalchemy import text

from .db import get_engine

log = logging.getLogger(__name__)


class EstadoSaude:
    """Compartilhado com o bot: vira pronto depois que o polling comeca."""

    def __init__(self) -> None:
        self.pronto = False


async def _healthz(_req: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


def _fabrica_readyz(estado: EstadoSaude):
    async def _readyz(_req: web.Request) -> web.Response:
        if not estado.pronto:
            return web.json_response({"status": "iniciando"}, status=503)
        try:
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001
            log.exception("readyz falhou")
            return web.json_response({"status": "erro", "erro": str(exc)}, status=503)
        return web.json_response({"status": "ok"})

    return _readyz


async def iniciar_servidor_health(porta: int, estado: EstadoSaude) -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/healthz", _healthz)
    app.router.add_get("/readyz", _fabrica_readyz(estado))

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=porta)
    await site.start()
    log.info("health server ouvindo em :%s", porta)
    return runner
