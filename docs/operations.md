# Operations

Docker, Kubernetes, CI and backup. To run it on your machine, see
[Development](development.md).

## Docker

```bash
just build     # builds the image
just scan      # Trivy: fails on HIGH/CRITICAL with a fix available
just smoke     # runs against a fake Bot API and validates the flow end to end
just up        # starts it for real (requires .env)
just check     # test + scan + smoke
```

The smoke test (`scripts/fake_telegram.py`, compose profile `smoke`) proves the
full path without touching the real Telegram: it delivers a scripted set of
updates, **including a resend**, and prints what the bot replied. The resend must
produce no reply, and the `/mes` summary at the end must count the expense only
once.

Image: multi-stage with uv, ~176 MB, non-root (uid 10001), read-only rootfs, all
capabilities dropped. `pip` is removed from the runtime — it is never used there,
and the code it vendors was the only source of HIGH findings in the scan.

## Kubernetes

```bash
just deploy-dry                          # validates without touching the cluster
just deploy                              # reads the .env and installs
just deploy -n financas -t v0.4.1 -i ghcr.io/rafalg18/caderneta
```

`scripts/deploy.sh` reads the same `.env` as docker compose, creates the
namespace, applies the token Secret and runs `helm upgrade --install`. The token
does **not** go through `--set`: it would become a process argument (visible in
`ps`) and would stay in the release history, which `helm get values` reads in
plain text — instead the script applies a Secret via stdin and installs with
`telegram.existingSecret`. The `.env` is read with a regex, not with `source`: a
configuration file should not be able to run a command.

The image comes from GHCR, published by CI on every push to `main` and on tags
(`ghcr.io/rafalg18/caderneta`). To run the one you built locally:

```bash
just build
just deploy -i caderneta -t local     # + load it into the cluster (kind load / minikube image load)
```

The manual path still works:

```bash
kubectl create secret generic caderneta-token --from-literal=BOT_TOKEN=<token>

helm install caderneta ./helm/caderneta \
  --set telegram.existingSecret=caderneta-token \
  --set telegram.ownerChatId=<your_chat_id> \
  --set image.repository=<your-registry>/caderneta \
  --set image.tag=v0.4.1
```

The chart **fails at render time** (before reaching the cluster) if you ask for
`replicaCount > 1`, an `accessMode` other than `ReadWriteOnce`, or forget the
token. The PVC has `helm.sh/resource-policy: keep` — the database does not
disappear on a `helm uninstall`.

Probes: `/healthz` (liveness) and `/readyz` (readiness, checks SQLite).

The container runs `alembic upgrade head` in the entrypoint before starting the
bot.

## CI

`.github/workflows/ci.yml`, in two jobs:

| Job | What runs | When |
|---|---|---|
| `qualidade` | `pytest`, `helm lint`, `helm template` | every push and PR |
| `imagem` | build, Trivy, smoke test, publish to GHCR | build/scan/smoke always; publishes only on `main` and `v*` tags |

The image is built **once** and it is the same one that goes through the scan,
the smoke test and into the registry — scanning a different artifact than the one
that reaches production proves nothing. The push uses the workflow's own
`GITHUB_TOKEN`, with no extra secret.

Published tags: the version with a `v` prefix (`v0.4.1`, `v0.4`) on a `v*` tag,
the full sha on every push, and `latest` on `main`. Prefer the sha or the version
when deploying: with `pullPolicy: IfNotPresent`, `latest` goes stale on the node
without warning.

The `v` prefix applies from `0.4.0` onwards. Earlier images were published
without it — to go back to one of those the tag is `0.3.0`, not `v0.3.0`.

Since the chart resolves `image.tag: ""` to `v` + `appVersion`, **the default
only exists in the registry after a `git tag`**: a push to `main` publishes
`main`/`sha`/`latest`, not the version. Before the first release, use
`just deploy -t latest`. CI fails if a `v*` tag does not match the `appVersion`
in `Chart.yaml`.

## Backup

```bash
DESTINATION=~/backups/caderneta ./scripts/backup.sh
```

It uses `sqlite3.backup` (a consistent copy), compresses the result, validates
the generated file and discards anything older than `KEEP_DAYS` (default 30).
The older `DESTINO` and `MANTER_DIAS` names still work, so an existing cron entry
does not break. Suggested cron:

```
0 3 * * * /path/to/scripts/backup.sh >> /var/log/caderneta-backup.log 2>&1
```
