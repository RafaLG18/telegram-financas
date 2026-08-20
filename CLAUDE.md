# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Telegram bot for personal finance tracking (single user, SQLite, polling).

The long-form documentation lives in [`docs/`](docs/) and is the source of truth:
do not duplicate it here, link to it. This file is only what an agent needs at
hand.

| I need… | Read |
|---|---|
| layers, the path of an update, data model | [docs/architecture.md](docs/architecture.md) |
| why a decision exists, before changing it | [docs/decisions.md](docs/decisions.md) |
| tests, migrations, release | [docs/development.md](docs/development.md) |
| Docker, Kubernetes, CI, backup | [docs/operations.md](docs/operations.md) |

## Language

Code is in English: identifiers, docstrings, comments, commit messages, docs and
the database schema. **Everything the user reads in Telegram stays in pt-BR** —
commands (`/registrar`, `/hoje`), messages, button labels, and the default
category names (`Mercado`, `Salário`). The parser's input words (`ontem`,
`anteontem`, `hoje`) are product too, so they stay in pt-BR. Keep that split.

## Commands

```bash
just setup                              # uv sync
just test                               # uv run pytest -q
uv run pytest tests/test_parse.py -q    # one file; -k <expr> for one test
just migrate                            # alembic upgrade head
just migration "add account"            # autogenerate from the models
uv run python -m caderneta.bot          # runs locally (needs .env with BOT_TOKEN)
just build / scan / smoke / up / logs   # docker
just check                              # test + scan + smoke - the full verification
just helm-lint / helm-render / deploy-dry
```

There is no linter configured (the `.ruff_cache` is a local leftover); CI runs
only `pytest`, `helm lint` and `helm template`.

## The boundary

`core/` does not import aiogram — the project's only architectural boundary. New
business rules go into `core/`; a handler only translates Telegram ↔ core.
`core/__init__.py` re-exports the public API of the domain modules.

## Invariants that break things when ignored

The *why* of each one is in [docs/decisions.md](docs/decisions.md).

- **Amount in integer cents, always positive**; the sign comes from
  `Transaction.kind`.
- **`source_update_id` is UNIQUE.** `record_transaction` returns
  `(transaction, created)`; `created=False` is a Telegram resend — the handler
  stays quiet, neither duplicating nor replying again. Every handler that writes
  passes the `update_id` (injected into `data` by the middleware).
- **`date` (of the fact, local tz) ≠ `created_at` (of the record, UTC).** "Today"
  comes from `dt.datetime.now(config.tz).date()`, never from `date.today()`.
- **A draft lives in the database**, with a short id that fits in the 64 bytes of
  `callback_data`.
- **Every reply to a callback edits the message removing the keyboard**
  (`_clear_keyboard` in `handlers/record.py`).
- **Router order matters**: `quick` is the text catch-all and comes last in
  `handlers/__init__.py::build_router`. A new router goes in before it.
- **Synchronous SQLAlchemy and 1 replica, always.**
- **`render_as_batch=True`** in `migrations/env.py`, or the generated migration
  will not apply on SQLite.
- **`session_scope()`**: pull text and ids out inside the block, before the
  `await`.

## Tests

Unit tests cover only `core/` and `parse.py` (`session` fixture: in-memory
SQLite, no Alembic). Handlers are covered end to end by the smoke test — changed
a handler flow, run `just smoke`.

## Commits

**Small commits, one concern each, every one tied to an issue.** A rename, a
behavior change and a doc update are three commits, not one — if the subject
needs an "and", split it. Every commit carries `Refs #N` in the body (`Closes #N`
on the one that finishes it), and leaves the tree working: tests pass at every
commit. Work with no issue yet gets one opened first. Details in
[docs/development.md](docs/development.md#commits).

## Release

**Every change becomes a tag and a release from `main`**: major `+0.1.0`, minor
`+0.0.1`. The version bump commit goes straight to `main`, no PR. Before tagging,
`pyproject.toml` and the `version`/`appVersion` in `Chart.yaml` must match the
tag, or CI fails. Step by step in
[docs/development.md](docs/development.md#release).
