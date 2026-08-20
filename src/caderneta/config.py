"""Configuration read from the environment. Fails early and with a clear message."""

from __future__ import annotations

import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    bot_token: str
    owner_chat_id: int | None
    db_path: str
    tz: ZoneInfo
    health_port: int
    log_level: str
    # Alternative Bot API endpoint (self-hosted Bot API or a test stub).
    # Empty = api.telegram.org.
    telegram_api_url: str | None = None

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path}"


def _int_or_none(raw: str | None) -> int | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"OWNER_CHAT_ID precisa ser numerico, veio {raw!r}") from exc


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise ConfigError(
            "BOT_TOKEN nao definido. Copie .env.example para .env e preencha "
            "com o token que o @BotFather te entregou."
        )

    tz_name = os.getenv("TZ", "America/Sao_Paulo").strip() or "America/Sao_Paulo"
    try:
        tz = ZoneInfo(tz_name)
    except Exception as exc:  # noqa: BLE001 - we want the friendly message
        raise ConfigError(f"TZ invalido: {tz_name!r}") from exc

    return Config(
        bot_token=token,
        owner_chat_id=_int_or_none(os.getenv("OWNER_CHAT_ID")),
        db_path=os.getenv("DB_PATH", "data/caderneta.db").strip(),
        tz=tz,
        health_port=int(os.getenv("HEALTH_PORT", "8080")),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
        telegram_api_url=os.getenv("TELEGRAM_API_URL", "").strip() or None,
    )
