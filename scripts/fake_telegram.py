"""Minimal stub of the Telegram Bot API, just for the smoke test.

It delivers a fixed script of updates and records what the bot replied, so that
docker compose can prove the full path:
  update -> handler -> business rule -> SQLite -> reply

This is not a unit-test mock: it is a network stand-in, used only by the compose
`smoke` profile. None of it goes into the production image.
"""

from __future__ import annotations

import json
import os
import time

from aiohttp import web

CHAT_ID = int(os.getenv("SMOKE_CHAT_ID", "12345"))

USER = {"id": CHAT_ID, "is_bot": False, "first_name": "Rafael"}
CHAT = {"id": CHAT_ID, "type": "private", "first_name": "Rafael"}

# Script: each item becomes one getUpdates batch, in order.
SCRIPT: list[list[dict]] = [
    [
        {
            "update_id": 1001,
            "message": {
                "message_id": 1,
                "date": int(time.time()),
                "chat": CHAT,
                "from": USER,
                "text": "50 mercado",
            },
        }
    ],
    [
        {
            "update_id": 1002,
            "message": {
                "message_id": 2,
                "date": int(time.time()),
                "chat": CHAT,
                "from": USER,
                "text": "+3000 salário",
            },
        }
    ],
    [
        # Resend of update 1001: the bot must NOT record the groceries again.
        {
            "update_id": 1001,
            "message": {
                "message_id": 1,
                "date": int(time.time()),
                "chat": CHAT,
                "from": USER,
                "text": "50 mercado",
            },
        }
    ],
    [
        {
            "update_id": 1003,
            "message": {
                "message_id": 3,
                "date": int(time.time()),
                "chat": CHAT,
                "from": USER,
                "text": "/mes",
            },
        }
    ],
]

state = {"batch": 0, "message_id": 100}
sent: list[dict] = []


async def _handler(request: web.Request) -> web.Response:
    method = request.match_info["method"]
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = dict(await request.post())

    if method == "getMe":
        return web.json_response(
            {
                "ok": True,
                "result": {
                    "id": 424242,
                    "is_bot": True,
                    "first_name": "Caderneta",
                    "username": "caderneta_smoke_bot",
                },
            }
        )

    if method == "getUpdates":
        i = state["batch"]
        if i < len(SCRIPT):
            state["batch"] += 1
            return web.json_response({"ok": True, "result": SCRIPT[i]})
        return web.json_response({"ok": True, "result": []})

    if method == "sendMessage":
        state["message_id"] += 1
        text = body.get("text", "")
        sent.append({"chat_id": body.get("chat_id"), "text": text})
        print(f"[fake-telegram] >>> {text}", flush=True)
        return web.json_response(
            {
                "ok": True,
                "result": {
                    "message_id": state["message_id"],
                    "date": int(time.time()),
                    "chat": CHAT,
                    "text": text,
                },
            }
        )

    if method in ("setMyCommands", "deleteWebhook", "answerCallbackQuery"):
        return web.json_response({"ok": True, "result": True})

    if method == "editMessageText":
        return web.json_response(
            {
                "ok": True,
                "result": {
                    "message_id": body.get("message_id", 1),
                    "date": int(time.time()),
                    "chat": CHAT,
                    "text": body.get("text", ""),
                },
            }
        )

    print(f"[fake-telegram] method nao implementado: {method}", flush=True)
    return web.json_response({"ok": True, "result": True})


async def _replies(_req: web.Request) -> web.Response:
    """Used by the smoke test to check what the bot replied."""
    return web.Response(
        text=json.dumps(sent, ensure_ascii=False, indent=2),
        content_type="application/json",
    )


def main() -> None:
    app = web.Application()
    app.router.add_route("*", "/bot{token}/{method}", _handler)
    app.router.add_get("/_replies", _replies)
    print("[fake-telegram] listening on :8081", flush=True)
    web.run_app(app, host="0.0.0.0", port=8081, print=None)


if __name__ == "__main__":
    main()
