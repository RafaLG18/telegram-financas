# Decisions

One section per decision that is not obvious: the context, the choice, and what
was discarded. If you are about to change one of them, this is where the reason
it exists is written down.

## Amount in integer cents, always positive

`Transaction.amount_cents` is an `int` with
`CheckConstraint("amount_cents > 0")`. The sign of the entry comes from `kind`
(`expense` / `income`), not from the number.

Floats get a cent wrong when summing a report, and a report that does not add up
destroys trust in the whole bot. Storing the sign in the amount would look
simpler, but it would scatter `abs()` across every formatting call and make `-0`
and `+0` representable.

**Discarded:** `Decimal` in the database (SQLite has no native decimal type — it
would end up as text or a float anyway). `Decimal` is used, but only inside
`parse.py`, in the conversion to cents.

## `date` separate from `created_at`

`date` is when it happened, in the local timezone; `created_at` is when it was
recorded, in UTC. They are different things: on Sunday you record what you spent
on Friday.

Practical consequence: "today" always comes from
`dt.datetime.now(config.tz).date()`, never from `date.today()` — the container
runs in UTC and the month would close three hours early every day.

## `source_update_id` UNIQUE

Telegram resends updates when it does not get an acknowledgement. With no
defense, one `50 mercado` becomes two entries, and the user only finds out at
the end of the month.

`record_transaction` checks `source_update_id` before inserting and returns
`(transaction, created)`; the UNIQUE's `IntegrityError` is the safety net for the
race. A handler that gets `created=False` stays quiet — replying again would be
worse than silence.

That is why polling does **not** use `drop_pending_updates`: the UNIQUE already
protects us, and this way nothing you sent while the bot was down is lost.

## Draft in the database, not in memory

The guided flow needs to carry state between messages. A dict in memory would be
one line of code.

Two things sink it: the state dies on every restart (and the bot restarts on
every deploy, in the middle of your entry), and Telegram's `callback_data` is
capped at 64 bytes — we need a short id pointing at the data, and an id only
exists if something persists it. `Draft.id` is `secrets.token_hex(4)`.

Abandoned drafts are purged at boot, above 24h.

## Editing the message to remove the keyboard

Every reply to a callback rewrites the message without the buttons. Telegram
keeps the conversation forever: without this, the button of an entry from three
days ago is still clickable, and nobody remembers what it was confirming.

## Synchronous SQLAlchemy in an async bot

Single user, local SQLite: each operation costs microseconds and the event loop
does not suffer. `aiosqlite` would require Alembic's async template and an async
session in every handler, buying nothing.

## One replica, always

Two pollers on the same token = `409 Conflict` on `getUpdates`, and SQLite
accepts a single writer. This is not a convention: the chart **fails at render
time** if `replicaCount > 1` or if `accessMode` is not `ReadWriteOnce`, before
anything reaches the cluster.

## `render_as_batch=True` in Alembic

SQLite has almost no `ALTER TABLE`. Without batch mode, autogenerate produces a
migration that only fails when applied — the error shows up far from its cause.

## Rule-based parsing, no LLM

`parse.py` is regex and `Decimal`: deterministic, testable and instant. One entry
recorded wrong through creative interpretation costs more than an honest "I did
not understand" — and the guided flow is always there as the main path.

## A one-chat_id whitelist

A Telegram bot is public by default: anyone who finds the @ can talk to it.
`OwnerOnly` is the only thing between your finances and a stranger. With no
`OWNER_CHAT_ID` configured the bot processes nothing — it only tells you your
`chat_id`, so you can fill it in and restart.

## Token through a Secret, never through `--set`

`scripts/deploy.sh` applies the Secret via stdin. A
`--set telegram.botToken=...` would become a process argument (visible in `ps`)
and would stay in the release history, which `helm get values` reads in plain
text.

For the same reason the `.env` is read with a regex and not with `source`: a
configuration file should not be able to run a command.

## One image, from build to registry

CI builds once and the same image goes through the scan, the smoke test and into
GHCR. A scan of a different artifact than the one that reaches production proves
nothing.

## English code, pt-BR product

Identifiers, docstrings, comments, docs and the database schema are in English.
Everything the user reads in Telegram is not: commands (`/registrar`, `/hoje`),
messages, button labels and the default category names (`Mercado`, `Salário`).
Translating those would change the product, not the language of the code. The
package name, `caderneta`, stays for the same reason.

The words the parser accepts as input (`ontem`, `anteontem`, `hoje`) are part of
the product too, so they stay in pt-BR.

## Out of scope for v1

Accounts (the `account_id` column already exists, null), budget per category,
tags, recurrence, editing an entry (only `/desfazer`), receipt attachment/OCR.
