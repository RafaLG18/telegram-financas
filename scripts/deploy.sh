#!/usr/bin/env bash
# Reads the .env and deploys the chart to Kubernetes.
#
# The token does NOT go through `--set`: it would become a process argument
# (visible in `ps`) and would be stored in the release history, which
# `helm get values` reads in plain text. Instead this script applies its own
# Secret and installs the chart pointing `telegram.existingSecret` at it - the
# path NOTES.txt recommends for production.
#
#   ./scripts/deploy.sh                       # uses .env, namespace caderneta
#   ./scripts/deploy.sh -n financas -t v1.2.0
#   ./scripts/deploy.sh --dry-run             # renders without touching the cluster
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART="$ROOT/helm/caderneta"

ENV_FILE="${ENV_FILE:-$ROOT/.env}"
NAMESPACE="${NAMESPACE:-caderneta}"
RELEASE="${RELEASE:-caderneta}"
SECRET_NAME="${SECRET_NAME:-caderneta-token}"
KUBE_CONTEXT="${KUBE_CONTEXT:-}"
IMAGE_REPOSITORY="${IMAGE_REPOSITORY:-}"
IMAGE_TAG="${IMAGE_TAG:-}"
TIMEOUT="${TIMEOUT:-5m}"
DRY_RUN=0

usage() {
    sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'
    cat <<'HELP'

Options:
  -f, --env-file FILE   .env file to read           (default: ./.env)
  -n, --namespace NS    cluster namespace           (default: caderneta)
  -r, --release NAME    Helm release name           (default: caderneta)
      --secret NAME     name of the token Secret    (default: caderneta-token)
      --context CTX     kubectl/helm context        (default: the current one)
  -i, --image REPO      overrides image.repository
  -t, --tag TAG         overrides image.tag
      --timeout DUR     rollout wait                (default: 5m)
      --dry-run         render and validate, applying nothing
  -h, --help            this help

All of them also accept an environment variable: ENV_FILE, NAMESPACE, RELEASE,
SECRET_NAME, KUBE_CONTEXT, IMAGE_REPOSITORY, IMAGE_TAG, TIMEOUT.
HELP
}

fail() { echo "[deploy] ERROR: $*" >&2; exit 1; }
info() { echo "[deploy] $*"; }
warn() { echo "[deploy] WARNING: $*" >&2; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        -f|--env-file)  ENV_FILE="$2"; shift 2 ;;
        -n|--namespace) NAMESPACE="$2"; shift 2 ;;
        -r|--release)   RELEASE="$2"; shift 2 ;;
        --secret)       SECRET_NAME="$2"; shift 2 ;;
        --context)      KUBE_CONTEXT="$2"; shift 2 ;;
        -i|--image)     IMAGE_REPOSITORY="$2"; shift 2 ;;
        -t|--tag)       IMAGE_TAG="$2"; shift 2 ;;
        --timeout)      TIMEOUT="$2"; shift 2 ;;
        --dry-run)      DRY_RUN=1; shift ;;
        -h|--help)      usage; exit 0 ;;
        *)              fail "unknown option: $1 (use --help)" ;;
    esac
done

# --------------------------------------------------------------------------
# Prerequisites
# --------------------------------------------------------------------------

for bin in helm kubectl; do
    command -v "$bin" >/dev/null || fail "$bin not found in PATH"
done
[[ -d "$CHART" ]] || fail "chart not found at $CHART"
[[ -f "$ENV_FILE" ]] || fail "$ENV_FILE does not exist (copy .env.example and fill it in)"

# A world-readable .env holds a bot token: worth the warning.
if [[ "$(stat -c '%a' "$ENV_FILE" 2>/dev/null || echo 600)" =~ [1-7]$ ]]; then
    warn "$ENV_FILE is readable by other users - consider chmod 600"
fi

KCTX=()
[[ -n "$KUBE_CONTEXT" ]] && KCTX=(--context "$KUBE_CONTEXT")

# --------------------------------------------------------------------------
# Reading the .env
#
# No `source`: the .env would become executable code, and a configuration file
# should not be able to run any command. Here only KEY=VALUE is matched.
# --------------------------------------------------------------------------

declare -A ENV_VARS=()
line_n=0
while IFS= read -r line || [[ -n "$line" ]]; do
    line_n=$((line_n + 1))
    line="${line%$'\r'}"                               # .env saved on Windows
    [[ -z "${line//[[:space:]]/}" || "$line" == \#* ]] && continue
    [[ "$line" == export\ * ]] && line="${line#export }"
    if [[ ! "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*=(.*)$ ]]; then
        warn "$ENV_FILE:$line_n ignored, does not look like KEY=VALUE"
        continue
    fi
    key="${BASH_REMATCH[1]}"
    value="${BASH_REMATCH[2]}"
    # Strip outer quotes; unquoted, cut a trailing comment.
    if [[ "$value" =~ ^\"(.*)\"[[:space:]]*$ || "$value" =~ ^\'(.*)\'[[:space:]]*$ ]]; then
        value="${BASH_REMATCH[1]}"
    else
        value="${value%%#*}"
        value="${value#"${value%%[![:space:]]*}"}"
        value="${value%"${value##*[![:space:]]}"}"
    fi
    ENV_VARS["$key"]="$value"
done < "$ENV_FILE"

env_value() { echo "${ENV_VARS[$1]-${2-}}"; }

BOT_TOKEN="$(env_value BOT_TOKEN)"
OWNER_CHAT_ID="$(env_value OWNER_CHAT_ID)"
TZ_APP="$(env_value TZ America/Sao_Paulo)"
LOG_LEVEL="$(env_value LOG_LEVEL INFO)"
DB_PATH="$(env_value DB_PATH /data/caderneta.db)"
HEALTH_PORT="$(env_value HEALTH_PORT 8080)"

[[ -n "$BOT_TOKEN" ]] || fail "BOT_TOKEN empty in $ENV_FILE"
# BotFather format: <numeric_id>:<secret>. Fail early instead of finding out
# in CrashLoopBackOff.
[[ "$BOT_TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]+$ ]] || fail "BOT_TOKEN does not look like a BotFather token"
if [[ -n "$OWNER_CHAT_ID" && ! "$OWNER_CHAT_ID" =~ ^-?[0-9]+$ ]]; then
    fail "OWNER_CHAT_ID must be numeric, got '$OWNER_CHAT_ID'"
fi
[[ -n "$OWNER_CHAT_ID" ]] || warn "OWNER_CHAT_ID empty - the bot starts in bootstrap mode and processes no commands"

VALUES=(
    --set-string "telegram.existingSecret=$SECRET_NAME"
    --set-string "telegram.existingSecretKey=BOT_TOKEN"
    --set-string "telegram.ownerChatId=$OWNER_CHAT_ID"
    --set-string "config.tz=$TZ_APP"
    --set-string "config.logLevel=$LOG_LEVEL"
    --set-string "config.dbPath=$DB_PATH"
    --set "config.healthPort=$HEALTH_PORT"
)
[[ -n "$IMAGE_REPOSITORY" ]] && VALUES+=(--set-string "image.repository=$IMAGE_REPOSITORY")
[[ -n "$IMAGE_TAG" ]] && VALUES+=(--set-string "image.tag=$IMAGE_TAG")

info "release=$RELEASE namespace=$NAMESPACE chart=$CHART"
info "TZ=$TZ_APP LOG_LEVEL=$LOG_LEVEL DB_PATH=$DB_PATH"

# --------------------------------------------------------------------------
# Dry-run: validates everything, touches no cluster
# --------------------------------------------------------------------------

if [[ $DRY_RUN -eq 1 ]]; then
    info "dry-run - rendering the chart (no resource will be applied)"
    helm lint "$CHART" --set "telegram.existingSecret=$SECRET_NAME" >/dev/null
    helm template "$RELEASE" "$CHART" --namespace "$NAMESPACE" "${VALUES[@]}"
    info "dry-run OK"
    exit 0
fi

# --------------------------------------------------------------------------
# Cluster
# --------------------------------------------------------------------------

kubectl "${KCTX[@]}" version -o yaml >/dev/null 2>&1 \
    || fail "no connection to the cluster (context: ${KUBE_CONTEXT:-$(kubectl config current-context 2>/dev/null || echo undefined)})"

if ! kubectl "${KCTX[@]}" get namespace "$NAMESPACE" >/dev/null 2>&1; then
    info "creating namespace $NAMESPACE"
    kubectl "${KCTX[@]}" create namespace "$NAMESPACE"
fi

# The manifest goes through stdin and the token is encoded by a shell builtin:
# that way it shows up neither in `ps` nor in a temporary file.
info "applying Secret $SECRET_NAME"
kubectl "${KCTX[@]}" apply -n "$NAMESPACE" -f - <<YAML >/dev/null
apiVersion: v1
kind: Secret
metadata:
  name: $SECRET_NAME
  labels:
    app.kubernetes.io/name: caderneta
    app.kubernetes.io/managed-by: deploy.sh
type: Opaque
data:
  BOT_TOKEN: $(printf '%s' "$BOT_TOKEN" | base64 | tr -d '\n')
YAML

info "helm upgrade --install"
helm "${KCTX[@]}" upgrade --install "$RELEASE" "$CHART" \
    --namespace "$NAMESPACE" \
    --create-namespace \
    "${VALUES[@]}" \
    --wait \
    --timeout "$TIMEOUT"

# --wait already waits, but rollout status prints the reason when it stalls.
if ! kubectl "${KCTX[@]}" rollout status -n "$NAMESPACE" \
        "deployment/$RELEASE" --timeout="$TIMEOUT"; then
    echo >&2
    warn "rollout did not complete. Latest events:"
    kubectl "${KCTX[@]}" get events -n "$NAMESPACE" \
        --sort-by=.lastTimestamp | tail -15 >&2
    exit 1
fi

info "up. Logs:"
echo "  kubectl ${KCTX[*]} logs -f -n $NAMESPACE -l app.kubernetes.io/instance=$RELEASE"
