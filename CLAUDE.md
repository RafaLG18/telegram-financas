# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Bot de Telegram para controle financeiro pessoal (uso individual, SQLite, polling).
O `README.md` documenta o produto e a operação (docker, k8s, backup) em detalhe — este
arquivo cobre o que é preciso saber para *mexer no código*.

## Idioma

Todo o projeto é em pt-BR: nomes de identificadores, docstrings, mensagens de commit,
textos de UI. Docstrings e comentários de código são escritos **sem acentos**; strings
que o usuário lê no Telegram usam acentuação normal. Mantenha essa convenção.

## Comandos

```bash
just setup                              # uv sync
just test                               # uv run pytest -q
uv run pytest tests/test_parse.py::test_nome -q   # um teste só
just migrate                            # alembic upgrade head (DB_PATH=data/caderneta.db)
just migration "adiciona conta"         # autogenerate a partir dos models
uv run python -m caderneta.bot          # roda local (precisa de .env com BOT_TOKEN)

just build / scan / smoke / up / logs   # docker
just check                              # test + scan + smoke — a verificação completa
just helm-lint / helm-render / deploy-dry
```

Não há linter configurado (o `.ruff_cache` é resíduo local); o CI roda apenas
`pytest`, `helm lint` e `helm template`.

## Arquitetura

```
Telegram ──polling──> handlers/ (aiogram) ──> core/ (regras) ──> SQLite (SQLAlchemy + Alembic)
```

**A única fronteira arquitetural do projeto: `core/` não importa aiogram.** É o que
permite testar as regras sem subir bot. Regra nova de negócio entra em `core/`; handler
só traduz Telegram ↔ core. `core/__init__.py` re-exporta a API pública dos módulos de
domínio (`categorias`, `transacoes`, `relatorios`, `rascunhos`) — importar do pacote ou
do módulo específico dá no mesmo.

Camadas de apoio no nível de `src/caderneta/`: `parse.py` (texto livre → valor/data/
descrição, determinístico, sem LLM), `textos.py` (formatação das mensagens),
`keyboards.py` (teclados inline + constantes de `callback_data`), `middlewares.py`
(whitelist `SomenteDono`), `config.py`, `db.py`, `health.py`, `models.py`.

### Invariantes que quebram coisas se ignoradas

- **Valor em centavos inteiros, sempre positivo.** O sinal vem de `Transacao.tipo`
  (`gasto`/`entrada`). Há `CheckConstraint` no banco.
- **`origem_update_id` é UNIQUE** e é a defesa contra update reenviado pelo Telegram.
  `registrar_transacao` devolve `(transacao, criada)`; `criada=False` significa reenvio —
  o handler deve sair calado, sem duplicar nem responder de novo. Todo handler que grava
  precisa passar o `update_id` (injetado em `data` pelo middleware).
- **`data` (do fato, fuso local) ≠ `criado_em` (do registro, UTC).** "Hoje" sempre sai de
  `dt.datetime.now(config.tz).date()`, nunca de `date.today()` no handler.
- **Rascunho vive no banco, não em memória.** O `id` curto (`secrets.token_hex(4)`) é o que
  cabe nos 64 bytes de `callback_data`; o dado real fica na tabela. Sobrevive a restart.
- **Toda resposta a callback edita a mensagem removendo o teclado** (`_limpar_teclado` em
  `handlers/registrar.py`) — evita o "botão zumbi" clicado dias depois.
- **Ordem dos routers importa.** `handlers/__init__.py::montar_router` registra `rapido`
  por último: ele é catch-all de texto (`F.text & ~F.text.startswith("/")`). Router novo
  entra *antes* dele.
- **SQLAlchemy síncrono e 1 réplica, sempre.** Dois pollers = `409 Conflict` no
  getUpdates; SQLite = um escritor. O chart falha no render se `replicaCount > 1`.
- **`render_as_batch=True`** no `migrations/env.py`: sem isso o Alembic gera migração que o
  SQLite não consegue aplicar.

### Acesso ao banco

`db.py` guarda engine/sessionmaker em módulo global; `init_engine()` precisa ter rodado
antes (`bot.py::preparar_banco`). Handlers usam `with session_scope() as sessao:` — commit
no sucesso, rollback na exceção. Objetos são `expire_on_commit=False`, mas **extraia o que
vai para a resposta (texto, ids) dentro do bloco** antes de fazer `await`. Pragmas ligados
na conexão: WAL, `foreign_keys=ON`, `busy_timeout=5000`.

## Testes

`tests/` cobre só `core/` e `parse.py` — a fixture `sessao` (conftest) dá um SQLite em
memória com `Base.metadata.create_all`, sem Alembic. Handlers não têm teste unitário: quem
cobre o caminho ponta a ponta é o smoke test (`scripts/fake_telegram.py`, profile `smoke`
do compose), que roda o bot contra uma Bot API falsa via `TELEGRAM_API_URL`, entrega
updates roteirizados **incluindo um reenvio**, e confere que o banco terminou com 2
lançamentos. Mudou fluxo de handler → rode `just smoke`.

## Versão e release

**Regra: toda alteração vira uma tag e uma release, cortadas a partir da `main`.** Não
existe mudança que entre na `main` sem release correspondente.

O incremento parte sempre da release anterior:

| Tipo de alteração | Incremento | Exemplo (a partir de `v0.4.0`) |
|---|---|---|
| Major (feature, mudança de comportamento) | `+0.1.0` | `v0.5.0` |
| Minor (correção, ajuste pontual) | `+0.0.1` | `v0.4.1` |

Antes de taggear, atualize **as duas versões** e faça o commit da versão na `main`:

- `pyproject.toml` → `version`
- `helm/caderneta/Chart.yaml` → `version` e `appVersion`

As duas precisam bater com a tag (sem o `v`) — o CI falha se divergirem, porque o chart
resolve `image.tag: ""` para `v` + `appVersion`. Tags com prefixo `v` valem a partir da
0.4.0; as anteriores foram publicadas sem ele.

```bash
git checkout main && git pull
# commit da versao em pyproject.toml e Chart.yaml
git tag v0.5.0 && git push origin main v0.5.0
gh release create v0.5.0 --title "v0.5.0" --notes "..."
```

A tag `v*` é o que dispara o job de publicação da imagem no GHCR.
