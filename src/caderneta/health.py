"""Health endpoint.

A polling bot opens no port at all, which would leave the Kubernetes probes with
nothing to measure. aiohttp already ships with aiogram, so this is free.
"""

from __future__ import annotations

import logging

from aiohttp import web
from sqlalchemy import text

from .db import get_engine

log = logging.getLogger(__name__)


class HealthState:
    """Shared with the bot: becomes ready once polling has started."""

    def __init__(self) -> None:
        self.ready = False


async def _healthz(_req: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


def _make_readyz(state: HealthState):
    async def _readyz(_req: web.Request) -> web.Response:
        if not state.ready:
            return web.json_response({"status": "starting"}, status=503)
        try:
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001
            log.exception("readyz failed")
            return web.json_response({"status": "error", "error": str(exc)}, status=503)
        return web.json_response({"status": "ok"})

    return _readyz


async def start_health_server(port: int, state: HealthState) -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/healthz", _healthz)
    app.router.add_get("/readyz", _make_readyz(state))

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    log.info("health server listening on :%s", port)
    return runner
