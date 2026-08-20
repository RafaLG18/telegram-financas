# Architecture

The *why* behind each choice lives in [Decisions](decisions.md); this is the *how*.

```
Telegram ──polling──> handlers/  ──> core/   ──> SQLite
                      (aiogram)      (rules)     (SQLAlchemy + Alembic)
```

## The boundary

`core/` does not import aiogram. It is the project's only architectural
boundary, and it is what lets the rules be tested without starting a bot and the
interface be swapped later. Inside it, one module per domain — `categories`,
`transactions`, `reports`, `drafts` — and `__init__` re-exports the public API,
so importing from the package or from the specific module is the same thing.

New business rules go into `core/`. A handler only translates Telegram ↔ core.

## Modules

| File | Role |
|---|---|
| `bot.py` | entry point: config, database, health server, polling |
| `middlewares.py` | `OwnerOnly` — the one-chat_id whitelist |
| `handlers/` | Telegram ↔ core translation, one router per area |
| `core/` | business rules, no aiogram |
| `models.py` | tables and the guided-flow states |
| `db.py` | engine, `session_scope`, SQLite pragmas |
| `parse.py` | free text → amount, date, description (deterministic, no LLM) |
| `texts.py` | message formatting |
| `keyboards.py` | inline keyboards and `callback_data` constants |
| `config.py` | environment → `Config`, failing early |
| `health.py` | `/healthz` and `/readyz` |

## The path of an update

1. **Middleware.** `OwnerOnly` compares the `chat_id` against `OWNER_CHAT_ID`;
   anything that does not match is dropped with a log line. With no
   `OWNER_CHAT_ID` the bot enters bootstrap mode: it only replies with your
   `chat_id`. The `update_id` is injected into `data` here — idempotency comes
   from it.
2. **Router.** `handlers/__init__.py::build_router` includes `start`, `record`,
   `reports` and, **last**, `quick`. Order matters: `quick` is the text
   catch-all (`F.text & ~F.text.startswith("/")`) and may only get what nobody
   else wanted. A new router goes in before it.
3. **Handler.** Opens `session_scope()`, calls `core`, pulls the reply text out
   while still inside the block, and only then awaits Telegram.
4. **Core.** `record_transaction` returns `(transaction, created)`.
   `created=False` means the update was resent: the handler stays quiet, neither
   duplicating nor confusing the user.

## The two ways to record

| Path | How it works |
|---|---|
| `/registrar` | guided flow; a `Draft` row carries the state (`S_KIND` → `S_AMOUNT` → `S_CATEGORY` → `S_CONFIRM`, with a detour to `S_FREE_DATE`) |
| `50 mercado` | `handlers/quick.py`: `parse_entry` extracts amount and date, the rest becomes the description and is matched against a category name |

Telegram's `callback_data` has a hard 64-byte limit, so buttons carry only short
pointers (`action:draft_id:value`) — the real data lives in the database. Every
reply to a callback edits the message removing the keyboard, which kills the
"zombie button" clicked days later.

## Database access

`db.py` keeps the engine and sessionmaker in module globals; `init_engine()`
must have run first (`bot.py::prepare_database`, which also seeds the categories
and purges abandoned drafts). Handlers use:

```python
with session_scope() as session:   # commit on success, rollback on exception
    ...
```

Objects are `expire_on_commit=False`, but **pull whatever goes into the reply
(text, ids) out inside the block**, before the `await`.

Pragmas set on every connection: `journal_mode=WAL` (backup and reads while the
bot writes), `foreign_keys=ON` (SQLite ignores FKs by default — without this the
model's `ForeignKey`s are decorative) and `busy_timeout=5000`.

## Data model

- `category` — unique name, `kind` in `expense`/`income`/`both`, `active`.
- `transaction` — `amount_cents` always positive (the sign comes from `kind`),
  `date` of the fact and `created_at` of the record, `source_update_id` UNIQUE,
  `account_id` reserved for v2.
- `draft` — entry under construction, short 8-hex id, deleted on completion and
  after 24h of abandonment.

Table and column names are in English; the values the user reads (category
names) are in pt-BR, like every Telegram-facing string.
