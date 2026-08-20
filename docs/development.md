# Development

Local setup is in the [README](../README.md#setup). This is the day-to-day of
working on the code.

## Commands

```bash
just setup                              # uv sync
just test                               # uv run pytest -q
uv run pytest tests/test_parse.py -q    # one file
uv run pytest -k amount -q              # one test
just migrate                            # applies the migrations
just migration "add account"            # generates a migration from the models
uv run python -m caderneta.bot          # runs the bot (requires .env)
just check                              # test + scan + smoke, the full verification
```

`just` on its own lists every recipe.

## Conventions

Code is in English: identifiers, docstrings, comments, commit messages and these
docs. Everything the user reads in Telegram stays in pt-BR — commands, messages,
button labels and the default category names. The reasoning is in
[Decisions](decisions.md#english-code-pt-br-product).

There is no linter configured — CI runs `pytest`, `helm lint` and
`helm template`.

## Tests

`tests/` covers `core/` and `parse.py`. The `session` fixture (in `conftest.py`)
gives an in-memory SQLite built with `Base.metadata.create_all`, no Alembic.

Handlers have no unit tests: the end-to-end path is covered by the smoke test,
which runs the real bot against a fake Bot API (`scripts/fake_telegram.py`, via
`TELEGRAM_API_URL`), delivers scripted updates **including a resend**, and prints
the replies. Changed a handler flow → run `just smoke`.

## Migrations

```bash
just migration "add account"   # generates from the models
just migrate                   # applies
```

`render_as_batch=True` is on in `env.py`: SQLite has almost no `ALTER TABLE`, and
without it Alembic generates a migration that fails when applied.

In production, the container entrypoint runs `alembic upgrade head` before
starting the bot.

Renaming a table or column in SQLite is not a plain `ALTER`: `batch_alter_table`
recreates the table from the *reflected* schema, dragging old CHECK constraints
along. When that matters, create the new table, copy with `INSERT ... SELECT` and
drop the old one — see
`migrations/versions/a7c4e91b2d38_translate_schema_to_english.py`.

## Release

**Every change becomes a tag and a release, cut from `main`.** The bump is always
relative to the previous release:

| Type of change | Bump | Example (from `v0.4.1`) |
|---|---|---|
| Major (feature, behavior change) | `+0.1.0` | `v0.5.0` |
| Minor (fix, small adjustment) | `+0.0.1` | `v0.4.2` |

Before tagging, update both versions and commit on `main`:

- `pyproject.toml` → `version`
- `helm/caderneta/Chart.yaml` → `version` and `appVersion`

Both must match the tag (without the `v`): CI fails if they diverge, because the
chart resolves `image.tag: ""` to `v` + `appVersion` — that is how one deploy
broke with `ImagePullBackOff`.

```bash
git checkout main && git pull
# commit the version in pyproject.toml and Chart.yaml
git tag v0.4.2 && git push origin main v0.4.2
gh release create v0.4.2 --title "v0.4.2" --notes "..."
```

The `v*` tag is what triggers publishing the image to GHCR. Tags with the `v`
prefix apply from 0.4.0 onwards.
