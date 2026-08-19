"""Stub minimo da Bot API do Telegram, so para o smoke test.

Entrega um roteiro fixo de updates e registra o que o bot respondeu, para que o
docker compose consiga provar o caminho completo:
  update -> handler -> regra de negocio -> SQLite -> resposta

Nao e um mock de teste unitario: e um dublê de rede, usado apenas pelo profile
`smoke` do compose. Nada disso entra na imagem de producao.
"""

from __future__ import annotations

import json
import os
import time

from aiohttp import web

CHAT_ID = int(os.getenv("SMOKE_CHAT_ID", "12345"))

USUARIO = {"id": CHAT_ID, "is_bot": False, "first_name": "Rafael"}
CHAT = {"id": CHAT_ID, "type": "private", "first_name": "Rafael"}

# Roteiro: cada item vira um lote de getUpdates, na ordem.
ROTEIRO: list[list[dict]] = [
    [
        {
            "update_id": 1001,
            "message": {
                "message_id": 1,
                "date": int(time.time()),
                "chat": CHAT,
                "from": USUARIO,
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
                "from": USUARIO,
                "text": "+3000 salário",
            },
        }
    ],
    [
        # Reenvio do update 1001: o bot NAO pode registrar o mercado de novo.
        {
            "update_id": 1001,
            "message": {
                "message_id": 1,
                "date": int(time.time()),
                "chat": CHAT,
                "from": USUARIO,
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
                "from": USUARIO,
                "text": "/mes",
            },
        }
    ],
]

estado = {"lote": 0, "message_id": 100}
enviadas: list[dict] = []


async def _handler(request: web.Request) -> web.Response:
    metodo = request.match_info["metodo"]
    try:
        corpo = await request.json()
    except Exception:  # noqa: BLE001
        corpo = dict(await request.post())

    if metodo == "getMe":
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

    if metodo == "getUpdates":
        i = estado["lote"]
        if i < len(ROTEIRO):
            estado["lote"] += 1
            return web.json_response({"ok": True, "result": ROTEIRO[i]})
        return web.json_response({"ok": True, "result": []})

    if metodo == "sendMessage":
        estado["message_id"] += 1
        texto = corpo.get("text", "")
        enviadas.append({"chat_id": corpo.get("chat_id"), "text": texto})
        print(f"[fake-telegram] >>> {texto}", flush=True)
        return web.json_response(
            {
                "ok": True,
                "result": {
                    "message_id": estado["message_id"],
                    "date": int(time.time()),
                    "chat": CHAT,
                    "text": texto,
                },
            }
        )

    if metodo in ("setMyCommands", "deleteWebhook", "answerCallbackQuery"):
        return web.json_response({"ok": True, "result": True})

    if metodo == "editMessageText":
        return web.json_response(
            {
                "ok": True,
                "result": {
                    "message_id": corpo.get("message_id", 1),
                    "date": int(time.time()),
                    "chat": CHAT,
                    "text": corpo.get("text", ""),
                },
            }
        )

    print(f"[fake-telegram] metodo nao implementado: {metodo}", flush=True)
    return web.json_response({"ok": True, "result": True})


async def _respostas(_req: web.Request) -> web.Response:
    """Usado pelo smoke test para conferir o que o bot respondeu."""
    return web.Response(
        text=json.dumps(enviadas, ensure_ascii=False, indent=2),
        content_type="application/json",
    )


def main() -> None:
    app = web.Application()
    app.router.add_route("*", "/bot{token}/{metodo}", _handler)
    app.router.add_get("/_respostas", _respostas)
    print("[fake-telegram] ouvindo em :8081", flush=True)
    web.run_app(app, host="0.0.0.0", port=8081, print=None)


if __name__ == "__main__":
    main()
