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

**Consultar**: `/hoje`, `/mes`, `/extrato`
**Corrigir**: `/desfazer` (remove o último), `/cancelar` (descarta um fluxo em andamento)

## Arquitetura em uma tela

```
Telegram ──polling──> handlers/  ──> core.py ──> SQLite
                      (aiogram)      (regras)    (SQLAlchemy + Alembic)
```

`core.py` não importa aiogram. É a única fronteira arquitetural do projeto, e
é o que permite testar as regras sem subir bot e trocar de interface depois.

Decisões que não são óbvias e o motivo:

| Decisão | Por quê |
|---|---|
| Valor em **centavos inteiros**, sempre positivo | float erra centavo em soma de relatório; o sinal vem de `tipo` |
| `data` (fato) separada de `criado_em` (registro) | você lança no domingo o que gastou na sexta |
| `origem_update_id` **UNIQUE** | o Telegram reenvia updates; sem isso um gasto vira dois |
| Rascunho no **banco**, não em memória | sobrevive a restart e dá o id curto que vai no `callback_data` |
| Sempre **editar a mensagem removendo o teclado** | mata o "botão zumbi" clicado dias depois |
| SQLAlchemy **síncrono** | usuário único e SQLite local: async custaria complexidade sem ganho |
| **1 réplica**, sempre | dois pollers = `409 Conflict` no getUpdates; SQLite = um escritor |

## Setup local

```bash
just setup                      # uv sync
cp .env.example .env            # preencha BOT_TOKEN
just migrate                    # cria o banco
uv run python -m caderneta.bot
```

Deixe `OWNER_CHAT_ID` vazio no primeiro boot: o bot responde com o seu `chat_id`.
Preencha, reinicie, e a whitelist passa a valer.

## Docker

```bash
just build     # builda a imagem
just scan      # Trivy: falha se houver HIGH/CRITICAL com correção disponível
just smoke     # sobe contra uma Bot API falsa e valida o fluxo ponta a ponta
just up        # sobe de verdade (exige .env)
just check     # test + scan + smoke
```

O smoke test (`scripts/fake_telegram.py`, profile `smoke` do compose) prova o
caminho completo sem tocar no Telegram real: entrega updates roteirizados,
**inclusive um reenvio**, e confere que o banco terminou com 2 lançamentos.

Imagem: multi-stage com uv, ~176 MB, non-root (uid 10001), rootfs read-only,
todas as capabilities dropadas. O `pip` é removido do runtime — não é usado e
o código que ele traz vendorizado era a única fonte de HIGH no scan.

## Kubernetes

```bash
just deploy-dry                          # valida sem tocar no cluster
just deploy                              # lê o .env e instala
just deploy -n financas -t 0.1.0 -i ghcr.io/rafalg18/caderneta
```

`scripts/deploy.sh` lê o mesmo `.env` do docker compose, cria o namespace,
aplica o Secret do token e roda `helm upgrade --install`. O token **não** passa
por `--set`: viraria argumento de processo (visível no `ps`) e ficaria no
histórico do release, que `helm get values` lê em texto puro — em vez disso o
script aplica um Secret por stdin e instala com `telegram.existingSecret`.
O `.env` é lido por regex, não por `source`: arquivo de configuração não
deveria poder executar comando.

A imagem vem do GHCR, publicada pelo CI a cada push no `main` e em tag
(`ghcr.io/rafalg18/caderneta`). Para subir a que voce buildou localmente:

```bash
just build
just deploy -i caderneta -t local     # + carregar no cluster (kind load / minikube image load)
```

O caminho manual continua valendo:

```bash
kubectl create secret generic caderneta-token --from-literal=BOT_TOKEN=<token>

helm install caderneta ./helm/caderneta \
  --set telegram.existingSecret=caderneta-token \
  --set telegram.ownerChatId=<seu_chat_id> \
  --set image.repository=<seu-registry>/caderneta \
  --set image.tag=0.1.0
```

O chart **falha no render** (antes de chegar no cluster) se você pedir
`replicaCount > 1`, `accessMode` diferente de `ReadWriteOnce`, ou esquecer o
token. O PVC tem `helm.sh/resource-policy: keep` — o banco não some num
`helm uninstall`.

Probes: `/healthz` (liveness) e `/readyz` (readiness, verifica o SQLite).

## CI

`.github/workflows/ci.yml`, em dois jobs:

| Job | O que roda | Quando |
|---|---|---|
| `qualidade` | `pytest`, `helm lint`, `helm template` | todo push e PR |
| `imagem` | build, Trivy, smoke test, publica no GHCR | build/scan/smoke sempre; publica só em `main` e tags `v*` |

A imagem é buildada **uma vez** e é a mesma que passa pelo scan, pelo smoke e
vai para o registry — scan em artefato diferente do que entra em produção não
prova nada. O push usa o `GITHUB_TOKEN` do próprio workflow, sem segredo extra.

Tags publicadas: a versão (`0.1.0`, `0.1`) em tag `v*`, o sha completo em todo
push, e `latest` no `main`. Prefira sha ou versão no deploy: com
`pullPolicy: IfNotPresent`, `latest` envelhece no node sem avisar.

## Migrações

```bash
just migration "adiciona conta"   # gera a partir dos models
just migrate                      # aplica
```

`render_as_batch=True` está ligado no `env.py`: o SQLite quase não tem
`ALTER TABLE`, e sem isso o Alembic gera migração que falha ao aplicar.

O container roda `alembic upgrade head` no entrypoint antes de subir o bot.

## Backup

```bash
DESTINO=~/backups/caderneta ./scripts/backup.sh
```

Usa `sqlite3.backup` (cópia consistente), comprime, valida o arquivo gerado e
descarta os mais velhos que `MANTER_DIAS` (padrão 30). Cron sugerido:

```
0 3 * * * /caminho/scripts/backup.sh >> /var/log/caderneta-backup.log 2>&1
```

## Fora do escopo da v1

Contas (a coluna `conta_id` já existe, nula), orçamento por categoria, tags,
recorrência, edição de lançamento (só `/desfazer`), anexo/OCR de nota.
