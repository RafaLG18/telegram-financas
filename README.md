# Caderneta

Telegram bot for personal finance tracking. Single user, SQLite, polling.

The bot speaks Portuguese — commands, messages and category names are in pt-BR,
because that is the product. The code and these docs are in English.

## Using the bot

**Recording** — two paths to the same operation:

| Path | When |
|---|---|
| `/registrar` | guided flow with buttons (kind → amount → category → confirmation) |
| `50 mercado` | text shortcut, for everyday use |

The shortcut accepts `50`, `50,90`, `R$ 1.250,00`, and relative dates (`ontem`,
`anteontem`, `15/08`). For income instead of an expense, start with `+`
(`+3000 salário`).

In the guided flow, **📅 Mudar data** offers today/yesterday/the day before and,
under **📅 Outra data**, accepts any typed date (`15/08`, `15/08/2025`, `ontem`).
A future date is refused; a date more than two years old goes through, but is
flagged in the preview.

**Querying**: `/hoje`, `/mes`, `/extrato`
**Fixing**: `/desfazer` (removes the last one), `/cancelar` (discards a flow in
progress)

## Setup

```bash
just setup                      # uv sync
cp .env.example .env            # fill in BOT_TOKEN
just migrate                    # creates the database
uv run python -m caderneta.bot
```

Leave `OWNER_CHAT_ID` empty on the first boot: the bot replies with your
`chat_id`. Fill it in, restart, and the whitelist takes effect.

## How it works

```
Telegram ──polling──> handlers/  ──> core/   ──> SQLite
                      (aiogram)      (rules)     (SQLAlchemy + Alembic)
```

`core/` does not import aiogram. It is the project's only architectural
boundary, and it is what lets the rules be tested without starting a bot and the
interface be swapped later.

## Documentation

| File | What is in it |
|---|---|
| [docs/architecture.md](docs/architecture.md) | layers, the path of an update, data model |
| [docs/decisions.md](docs/decisions.md) | why integer cents, drafts in the database, one replica… |
| [docs/development.md](docs/development.md) | commands, tests, migrations, release flow |
| [docs/operations.md](docs/operations.md) | Docker, Kubernetes, CI, backup |
| [CLAUDE.md](CLAUDE.md) | the same, condensed for coding agents |

## Out of scope for v1

Accounts (the `account_id` column already exists, null), budget per category,
tags, recurrence, editing an entry (only `/desfazer`), receipt attachment/OCR.
