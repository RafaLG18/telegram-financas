# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Bot de Telegram para controle financeiro pessoal (uso individual, SQLite, polling).

A documentação longa vive em [`docs/`](docs/) e é a fonte da verdade: não duplique
aqui o que está lá, linke. Este arquivo é só o que um agente precisa ter à mão.

| Preciso de… | Leia |
|---|---|
| camadas, caminho de um update, modelo de dados | [docs/arquitetura.md](docs/arquitetura.md) |
| por que uma decisão existe, antes de mudá-la | [docs/decisoes.md](docs/decisoes.md) |
| testes, migrações, release | [docs/desenvolvimento.md](docs/desenvolvimento.md) |
| Docker, Kubernetes, CI, backup | [docs/operacao.md](docs/operacao.md) |

## Idioma

Todo o projeto é em pt-BR: identificadores, docstrings, mensagens de commit,
textos de UI. Docstrings e comentários de código são escritos **sem acentos**;
strings que o usuário lê no Telegram usam acentuação normal. Mantenha isso.

## Comandos

```bash
just setup                              # uv sync
just test                               # uv run pytest -q
uv run pytest tests/test_parse.py -q    # um arquivo; -k <expr> para um teste
just migrate                            # alembic upgrade head
just migration "adiciona conta"         # autogenerate a partir dos models
uv run python -m caderneta.bot          # roda local (precisa de .env com BOT_TOKEN)
just build / scan / smoke / up / logs   # docker
just check                              # test + scan + smoke — a verificação completa
just helm-lint / helm-render / deploy-dry
```

Não há linter configurado (o `.ruff_cache` é resíduo local); o CI roda apenas
`pytest`, `helm lint` e `helm template`.

## A fronteira

`core/` não importa aiogram — é a única fronteira arquitetural do projeto.
Regra nova de negócio entra em `core/`; handler só traduz Telegram ↔ core.
`core/__init__.py` re-exporta a API pública dos módulos de domínio.

## Invariantes que quebram coisas se ignoradas

O *porquê* de cada uma está em [docs/decisoes.md](docs/decisoes.md).

- **Valor em centavos inteiros, sempre positivo**; o sinal vem de `Transacao.tipo`.
- **`origem_update_id` é UNIQUE.** `registrar_transacao` devolve
  `(transacao, criada)`; `criada=False` é reenvio do Telegram — o handler sai
  calado, sem duplicar nem responder de novo. Todo handler que grava passa o
  `update_id` (injetado em `data` pelo middleware).
- **`data` (do fato, fuso local) ≠ `criado_em` (do registro, UTC).** "Hoje" sai de
  `dt.datetime.now(config.tz).date()`, nunca de `date.today()`.
- **Rascunho vive no banco**, com id curto que cabe nos 64 bytes de `callback_data`.
- **Toda resposta a callback edita a mensagem removendo o teclado**
  (`_limpar_teclado` em `handlers/registrar.py`).
- **Ordem dos routers importa**: `rapido` é catch-all de texto e fica por último
  em `handlers/__init__.py::montar_router`. Router novo entra antes dele.
- **SQLAlchemy síncrono e 1 réplica, sempre.**
- **`render_as_batch=True`** no `migrations/env.py`, senão a migração gerada não
  aplica no SQLite.
- **`session_scope()`**: extraia texto e ids de dentro do bloco antes do `await`.

## Testes

Unitários cobrem só `core/` e `parse.py` (fixture `sessao`: SQLite em memória,
sem Alembic). Handlers são cobertos ponta a ponta pelo smoke test — mexeu em
fluxo de handler, rode `just smoke`.

## Release

**Toda alteração vira tag e release a partir da `main`**: major `+0.1.0`, minor
`+0.0.1`. O commit de bump vai direto na `main`, sem PR. Antes de taggear,
`pyproject.toml` e `version`/`appVersion` do `Chart.yaml` precisam bater com a
tag, ou o CI falha. Passo a passo em
[docs/desenvolvimento.md](docs/desenvolvimento.md#release).
