# Operação

Docker, Kubernetes, CI e backup. Para rodar na sua máquina, veja
[Desenvolvimento](desenvolvimento.md).

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
just deploy -n financas -t v0.4.1 -i ghcr.io/rafalg18/caderneta
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
  --set image.tag=v0.4.1
```

O chart **falha no render** (antes de chegar no cluster) se você pedir
`replicaCount > 1`, `accessMode` diferente de `ReadWriteOnce`, ou esquecer o
token. O PVC tem `helm.sh/resource-policy: keep` — o banco não some num
`helm uninstall`.

Probes: `/healthz` (liveness) e `/readyz` (readiness, verifica o SQLite).

O container roda `alembic upgrade head` no entrypoint antes de subir o bot.

## CI

`.github/workflows/ci.yml`, em dois jobs:

| Job | O que roda | Quando |
|---|---|---|
| `qualidade` | `pytest`, `helm lint`, `helm template` | todo push e PR |
| `imagem` | build, Trivy, smoke test, publica no GHCR | build/scan/smoke sempre; publica só em `main` e tags `v*` |

A imagem é buildada **uma vez** e é a mesma que passa pelo scan, pelo smoke e
vai para o registry — scan em artefato diferente do que entra em produção não
prova nada. O push usa o `GITHUB_TOKEN` do próprio workflow, sem segredo extra.

Tags publicadas: a versão com prefixo `v` (`v0.4.1`, `v0.4`) em tag `v*`, o sha completo em todo
push, e `latest` no `main`. Prefira sha ou versão no deploy: com
`pullPolicy: IfNotPresent`, `latest` envelhece no node sem avisar.

O prefixo `v` vale a partir da `0.4.0`. As imagens anteriores foram publicadas
sem ele — para voltar a uma delas a tag é `0.3.0`, não `v0.3.0`.

Como o chart resolve `image.tag: ""` para `v` + `appVersion`, **o default só existe
no registry depois de um `git tag`**: push no `main` publica `main`/`sha`/`latest`,
não a versão. Antes do primeiro release, use `just deploy -t latest`. O CI falha
se uma tag `v*` não bater com o `appVersion` do `Chart.yaml`.

## Backup

```bash
DESTINO=~/backups/caderneta ./scripts/backup.sh
```

Usa `sqlite3.backup` (cópia consistente), comprime, valida o arquivo gerado e
descarta os mais velhos que `MANTER_DIAS` (padrão 30). Cron sugerido:

```
0 3 * * * /caminho/scripts/backup.sh >> /var/log/caderneta-backup.log 2>&1
```
