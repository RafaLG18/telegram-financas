image := "caderneta:local"
chart := "helm/caderneta"

# List the available recipes
default:
    @just --list

# Install dependencies with uv
setup:
    uv sync

# Run the tests
test:
    uv run pytest -q

# Build the image
build:
    docker build -t {{ image }} .

# Vulnerability scan (fails on HIGH/CRITICAL with a fix available)
scan: build
    docker compose --profile scan run --rm trivy

# Run the bot against a fake Bot API and validate the flow end to end
smoke: build
    docker compose --profile smoke up -d
    sleep 10
    @echo "--- bot replies ---"
    curl -s http://127.0.0.1:8081/_replies | python3 -m json.tool

# Tear down the smoke test environment (volume included)
smoke-down:
    docker compose --profile smoke down -v

# Start the real bot (requires a filled .env)
up:
    docker compose up -d bot

# Stop the bot
down:
    docker compose down

# Follow the logs
logs:
    docker compose logs -f bot

# Generate a migration from the models: just migration "add account"
migration message:
    DB_PATH=data/caderneta.db uv run alembic revision --autogenerate -m "{{ message }}"

# Apply the migrations locally
migrate:
    DB_PATH=data/caderneta.db uv run alembic upgrade head

# Lint the chart
helm-lint:
    helm lint {{ chart }} --set telegram.botToken=fake

# Render the chart
helm-render:
    helm template caderneta {{ chart }} --set telegram.existingSecret=caderneta-token

# Deploy to k8s reading the .env (helm upgrade --install)
deploy *args:
    ./scripts/deploy.sh {{ args }}

# Validate the deploy without touching the cluster
deploy-dry:
    ./scripts/deploy.sh --dry-run

# Full verification: tests + build + scan + smoke
check: test scan smoke

# Remove local artifacts
clean:
    rm -rf .pytest_cache data/caderneta.db
    find . -name __pycache__ -type d -prune -exec rm -rf {} +
