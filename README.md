# Caderneta

Bot de Telegram para controle financeiro pessoal. Uso individual, SQLite, polling.

## Como usar o bot

**Registrar** — dois caminhos para a mesma operação:

| Caminho | Quando |
|---|---|
| `/registrar` | fluxo guiado com botões (tipo → valor → categoria → confirmação) |
| `50 mercado` | atalho de texto, para o dia a dia |

O atalho aceita `50`, `50,90`, `R$ 1.250,00`, e datas relativas (`ontem`,
`anteontem`, `15/08`). Entrada em vez de gasto: comece com `+` (`+3000 salário`).

No fluxo guiado, **📅 Mudar data** oferece hoje/ontem/anteontem e, em
**📅 Outra data**, aceita qualquer data digitada (`15/08`, `15/08/2025`,
`ontem`). Data futura é recusada; data de mais de dois anos atrás passa, mas
sai marcada na prévia.

**Consultar**: `/hoje`, `/mes`, `/extrato`
**Corrigir**: `/desfazer` (remove o último), `/cancelar` (descarta um fluxo em andamento)

## Setup local

```bash
just setup                      # uv sync
cp .env.example .env            # preencha BOT_TOKEN
just migrate                    # cria o banco
uv run python -m caderneta.bot
```

Deixe `OWNER_CHAT_ID` vazio no primeiro boot: o bot responde com o seu `chat_id`.
Preencha, reinicie, e a whitelist passa a valer.

## Como funciona

```
Telegram ──polling──> handlers/  ──> core/   ──> SQLite
                      (aiogram)      (regras)    (SQLAlchemy + Alembic)
```

`core/` não importa aiogram. É a única fronteira arquitetural do projeto, e é o
que permite testar as regras sem subir bot e trocar de interface depois.

## Documentação

| Arquivo | O que tem |
|---|---|
| [docs/arquitetura.md](docs/arquitetura.md) | camadas, caminho de um update, modelo de dados |
| [docs/decisoes.md](docs/decisoes.md) | por que centavos inteiros, rascunho no banco, uma réplica… |
| [docs/desenvolvimento.md](docs/desenvolvimento.md) | comandos, testes, migrações, fluxo de release |
| [docs/operacao.md](docs/operacao.md) | Docker, Kubernetes, CI, backup |
| [CLAUDE.md](CLAUDE.md) | o mesmo, condensado para agentes de código |

## Fora do escopo da v1

Contas (a coluna `conta_id` já existe, nula), orçamento por categoria, tags,
recorrência, edição de lançamento (só `/desfazer`), anexo/OCR de nota.
