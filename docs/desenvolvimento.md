# Desenvolvimento

Setup local está no [README](../README.md#setup-local). Aqui é o dia a dia de
quem mexe no código.

## Comandos

```bash
just setup                              # uv sync
just test                               # uv run pytest -q
uv run pytest tests/test_parse.py -q    # um arquivo
uv run pytest -k valor -q               # um teste
just migrate                            # aplica as migrações
just migration "adiciona conta"         # gera migração a partir dos models
uv run python -m caderneta.bot          # roda o bot (precisa de .env)
just check                              # test + scan + smoke, a verificação completa
```

`just` sozinho lista todas as receitas.

## Convenções

O projeto é todo em pt-BR: identificadores, docstrings, mensagens de commit,
textos de UI. Docstrings e comentários de código são escritos **sem acentos**;
strings que o usuário lê no Telegram usam acentuação normal.

Não há linter configurado — o CI roda `pytest`, `helm lint` e `helm template`.

## Testes

`tests/` cobre `core/` e `parse.py`. A fixture `sessao` (em `conftest.py`) dá um
SQLite em memória com `Base.metadata.create_all`, sem Alembic.

Handlers não têm teste unitário: quem cobre o caminho ponta a ponta é o smoke
test, que roda o bot de verdade contra uma Bot API falsa
(`scripts/fake_telegram.py`, via `TELEGRAM_API_URL`), entrega updates
roteirizados **incluindo um reenvio**, e confere que o banco terminou com 2
lançamentos. Mexeu em fluxo de handler → rode `just smoke`.

## Migrações

```bash
just migration "adiciona conta"   # gera a partir dos models
just migrate                      # aplica
```

`render_as_batch=True` está ligado no `env.py`: o SQLite quase não tem
`ALTER TABLE`, e sem isso o Alembic gera migração que falha ao aplicar.

Em produção, o entrypoint do container roda `alembic upgrade head` antes de
subir o bot.

## Release

**Toda alteração vira uma tag e uma release, cortadas a partir da `main`.** O
incremento parte sempre da release anterior:

| Tipo de alteração | Incremento | Exemplo (a partir de `v0.4.1`) |
|---|---|---|
| Major (feature, mudança de comportamento) | `+0.1.0` | `v0.5.0` |
| Minor (correção, ajuste pontual) | `+0.0.1` | `v0.4.2` |

Antes de taggear, atualize as duas versões e faça o commit na `main`:

- `pyproject.toml` → `version`
- `helm/caderneta/Chart.yaml` → `version` e `appVersion`

As duas precisam bater com a tag (sem o `v`): o CI falha se divergirem, porque o
chart resolve `image.tag: ""` para `v` + `appVersion` — foi assim que um deploy
quebrou com `ImagePullBackOff`.

```bash
git checkout main && git pull
# commit da versao em pyproject.toml e Chart.yaml
git tag v0.4.2 && git push origin main v0.4.2
gh release create v0.4.2 --title "v0.4.2" --notes "..."
```

A tag `v*` é o que dispara a publicação da imagem no GHCR. Tags com prefixo `v`
valem a partir da 0.4.0.
