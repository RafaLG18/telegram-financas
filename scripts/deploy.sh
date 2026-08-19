#!/usr/bin/env bash
# Le o .env e faz o deploy do chart no Kubernetes.
#
# O token NAO vai por `--set`: ele viraria argumento de processo (visivel no
# `ps`) e ficaria gravado no historico do release, que o `helm get values` le em
# texto puro. Em vez disso o script aplica um Secret proprio e instala o chart
# apontando `telegram.existingSecret` pra ele — o caminho que o NOTES.txt
# recomenda pra producao.
#
#   ./scripts/deploy.sh                       # usa .env, namespace caderneta
#   ./scripts/deploy.sh -n financas -t v1.2.0
#   ./scripts/deploy.sh --dry-run             # renderiza sem tocar no cluster
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART="$RAIZ/helm/caderneta"

ENV_FILE="${ENV_FILE:-$RAIZ/.env}"
NAMESPACE="${NAMESPACE:-caderneta}"
RELEASE="${RELEASE:-caderneta}"
SECRET_NAME="${SECRET_NAME:-caderneta-token}"
KUBE_CONTEXT="${KUBE_CONTEXT:-}"
IMAGE_REPOSITORY="${IMAGE_REPOSITORY:-}"
IMAGE_TAG="${IMAGE_TAG:-}"
TIMEOUT="${TIMEOUT:-5m}"
DRY_RUN=0

uso() {
    sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'
    cat <<'AJUDA'

Opcoes:
  -f, --env-file ARQ    arquivo .env a ler          (padrao: ./.env)
  -n, --namespace NS    namespace do cluster        (padrao: caderneta)
  -r, --release NOME    nome do release Helm        (padrao: caderneta)
      --secret NOME     nome do Secret do token     (padrao: caderneta-token)
      --context CTX     contexto do kubectl/helm    (padrao: o atual)
  -i, --image REPO      sobrescreve image.repository
  -t, --tag TAG         sobrescreve image.tag
      --timeout DUR     espera do rollout           (padrao: 5m)
      --dry-run         renderiza e valida, sem aplicar nada
  -h, --help            esta ajuda

Todas tambem aceitam variavel de ambiente: ENV_FILE, NAMESPACE, RELEASE,
SECRET_NAME, KUBE_CONTEXT, IMAGE_REPOSITORY, IMAGE_TAG, TIMEOUT.
AJUDA
}

erro() { echo "[deploy] ERRO: $*" >&2; exit 1; }
info() { echo "[deploy] $*"; }
aviso() { echo "[deploy] AVISO: $*" >&2; }

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
        -h|--help)      uso; exit 0 ;;
        *)              erro "opcao desconhecida: $1 (use --help)" ;;
    esac
done

# --------------------------------------------------------------------------
# Pre-requisitos
# --------------------------------------------------------------------------

for bin in helm kubectl; do
    command -v "$bin" >/dev/null || erro "$bin nao encontrado no PATH"
done
[[ -d "$CHART" ]] || erro "chart nao encontrado em $CHART"
[[ -f "$ENV_FILE" ]] || erro "$ENV_FILE nao existe (copie o .env.example e preencha)"

# Um .env legivel por todo mundo guarda um token de bot: vale o alerta.
if [[ "$(stat -c '%a' "$ENV_FILE" 2>/dev/null || echo 600)" =~ [1-7]$ ]]; then
    aviso "$ENV_FILE esta legivel por outros usuarios — considere chmod 600"
fi

KCTX=()
[[ -n "$KUBE_CONTEXT" ]] && KCTX=(--context "$KUBE_CONTEXT")

# --------------------------------------------------------------------------
# Leitura do .env
#
# Sem `source`: o .env viraria codigo executavel, e um arquivo de configuracao
# nao deveria poder rodar comando nenhum. Aqui so casa KEY=VALUE.
# --------------------------------------------------------------------------

declare -A ENV_VARS=()
linha_n=0
while IFS= read -r linha || [[ -n "$linha" ]]; do
    linha_n=$((linha_n + 1))
    linha="${linha%$'\r'}"                             # .env salvo no Windows
    [[ -z "${linha//[[:space:]]/}" || "$linha" == \#* ]] && continue
    [[ "$linha" == export\ * ]] && linha="${linha#export }"
    if [[ ! "$linha" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*=(.*)$ ]]; then
        aviso "$ENV_FILE:$linha_n ignorada, nao parece KEY=VALUE"
        continue
    fi
    chave="${BASH_REMATCH[1]}"
    valor="${BASH_REMATCH[2]}"
    # Tira aspas externas; sem aspas, corta comentario no fim da linha.
    if [[ "$valor" =~ ^\"(.*)\"[[:space:]]*$ || "$valor" =~ ^\'(.*)\'[[:space:]]*$ ]]; then
        valor="${BASH_REMATCH[1]}"
    else
        valor="${valor%%#*}"
        valor="${valor#"${valor%%[![:space:]]*}"}"
        valor="${valor%"${valor##*[![:space:]]}"}"
    fi
    ENV_VARS["$chave"]="$valor"
done < "$ENV_FILE"

valor_de() { echo "${ENV_VARS[$1]-${2-}}"; }

BOT_TOKEN="$(valor_de BOT_TOKEN)"
OWNER_CHAT_ID="$(valor_de OWNER_CHAT_ID)"
TZ_APP="$(valor_de TZ America/Sao_Paulo)"
LOG_LEVEL="$(valor_de LOG_LEVEL INFO)"
DB_PATH="$(valor_de DB_PATH /data/caderneta.db)"
HEALTH_PORT="$(valor_de HEALTH_PORT 8080)"

[[ -n "$BOT_TOKEN" ]] || erro "BOT_TOKEN vazio em $ENV_FILE"
# Formato do BotFather: <id_numerico>:<segredo>. Erra cedo, em vez de descobrir
# no CrashLoopBackOff.
[[ "$BOT_TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]+$ ]] || erro "BOT_TOKEN nao parece um token do BotFather"
if [[ -n "$OWNER_CHAT_ID" && ! "$OWNER_CHAT_ID" =~ ^-?[0-9]+$ ]]; then
    erro "OWNER_CHAT_ID precisa ser numerico, veio '$OWNER_CHAT_ID'"
fi
[[ -n "$OWNER_CHAT_ID" ]] || aviso "OWNER_CHAT_ID vazio — o bot sobe em modo bootstrap e nao processa comandos"

VALORES=(
    --set-string "telegram.existingSecret=$SECRET_NAME"
    --set-string "telegram.existingSecretKey=BOT_TOKEN"
    --set-string "telegram.ownerChatId=$OWNER_CHAT_ID"
    --set-string "config.tz=$TZ_APP"
    --set-string "config.logLevel=$LOG_LEVEL"
    --set-string "config.dbPath=$DB_PATH"
    --set "config.healthPort=$HEALTH_PORT"
)
[[ -n "$IMAGE_REPOSITORY" ]] && VALORES+=(--set-string "image.repository=$IMAGE_REPOSITORY")
[[ -n "$IMAGE_TAG" ]] && VALORES+=(--set-string "image.tag=$IMAGE_TAG")

info "release=$RELEASE namespace=$NAMESPACE chart=$CHART"
info "TZ=$TZ_APP LOG_LEVEL=$LOG_LEVEL DB_PATH=$DB_PATH"

# --------------------------------------------------------------------------
# Dry-run: valida tudo, nao toca no cluster
# --------------------------------------------------------------------------

if [[ $DRY_RUN -eq 1 ]]; then
    info "dry-run — renderizando o chart (nenhum recurso sera aplicado)"
    helm lint "$CHART" --set "telegram.existingSecret=$SECRET_NAME" >/dev/null
    helm template "$RELEASE" "$CHART" --namespace "$NAMESPACE" "${VALORES[@]}"
    info "dry-run OK"
    exit 0
fi

# --------------------------------------------------------------------------
# Cluster
# --------------------------------------------------------------------------

kubectl "${KCTX[@]}" version -o yaml >/dev/null 2>&1 \
    || erro "sem conexao com o cluster (contexto: ${KUBE_CONTEXT:-$(kubectl config current-context 2>/dev/null || echo indefinido)})"

if ! kubectl "${KCTX[@]}" get namespace "$NAMESPACE" >/dev/null 2>&1; then
    info "criando namespace $NAMESPACE"
    kubectl "${KCTX[@]}" create namespace "$NAMESPACE"
fi

# O manifesto vai por stdin, e o token e codificado por builtin do shell: assim
# ele nao aparece em `ps` nem em arquivo temporario.
info "aplicando Secret $SECRET_NAME"
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
    "${VALORES[@]}" \
    --wait \
    --timeout "$TIMEOUT"

# --wait ja espera, mas o rollout status imprime o motivo quando trava.
if ! kubectl "${KCTX[@]}" rollout status -n "$NAMESPACE" \
        "deployment/$RELEASE" --timeout="$TIMEOUT"; then
    echo >&2
    aviso "rollout nao completou. Ultimos eventos:"
    kubectl "${KCTX[@]}" get events -n "$NAMESPACE" \
        --sort-by=.lastTimestamp | tail -15 >&2
    exit 1
fi

info "no ar. Logs:"
echo "  kubectl ${KCTX[*]} logs -f -n $NAMESPACE -l app.kubernetes.io/instance=$RELEASE"
