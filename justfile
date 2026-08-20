image := "caderneta:local"
chart := "helm/caderneta"

# Lista as receitas disponiveis
default:
    @just --list

# Instala dependencias com uv
setup:
    uv sync

# Roda os testes
test:
    uv run pytest -q

# Builda a imagem
build:
    docker build -t {{ image }} .

# Scan de vulnerabilidades (falha se houver HIGH/CRITICAL com correcao disponivel)
scan: build
    docker compose --profile scan run --rm trivy

# Sobe o bot contra uma Bot API falsa e valida o fluxo ponta a ponta
smoke: build
    docker compose --profile smoke up -d
    sleep 10
    @echo "--- respostas do bot ---"
    curl -s http://127.0.0.1:8081/_replies | python3 -m json.tool

# Derruba o ambiente de smoke test (inclusive o volume)
smoke-down:
    docker compose --profile smoke down -v

# Sobe o bot de verdade (exige .env preenchido)
up:
    docker compose up -d bot

# Derruba o bot
down:
    docker compose down

# Acompanha os logs
logs:
    docker compose logs -f bot

# Gera migracao a partir dos models: just migration "adiciona conta"
migration mensagem:
    DB_PATH=data/caderneta.db uv run alembic revision --autogenerate -m "{{ mensagem }}"

# Aplica as migracoes localmente
migrate:
    DB_PATH=data/caderneta.db uv run alembic upgrade head

# Lint do chart
helm-lint:
    helm lint {{ chart }} --set telegram.botToken=fake

# Renderiza o chart
helm-render:
    helm template caderneta {{ chart }} --set telegram.existingSecret=caderneta-token

# Deploy no k8s lendo o .env (helm upgrade --install)
deploy *args:
    ./scripts/deploy.sh {{ args }}

# Valida o deploy sem tocar no cluster
deploy-dry:
    ./scripts/deploy.sh --dry-run

# Verificacao completa: testes + build + scan + smoke
check: test scan smoke

# Remove artefatos locais
clean:
    rm -rf .pytest_cache data/caderneta.db
    find . -name __pycache__ -type d -prune -exec rm -rf {} +
