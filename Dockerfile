# syntax=docker/dockerfile:1.7

# ---------------------------------------------------------------------------
# Builder: resolves the dependencies with uv from the lock file, without
# installing the project (the code comes in through PYTHONPATH, which keeps the
# final image simple).
# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------
FROM python:3.13-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    DB_PATH=/data/caderneta.db \
    HEALTH_PORT=8080

# Upgrades whatever the base image ships with a known CVE and installs nothing
# else.
#
# pip goes away too: the venv arrives ready from the builder, so pip is never
# used at runtime - and the code it vendors (msgpack, setuptools) is exactly what
# showed up as HIGH in the Trivy scan. Removing it is more honest than adding an
# exception to .trivyignore.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /usr/local/lib/python3.*/site-packages/pip \
              /usr/local/lib/python3.*/site-packages/pip-*.dist-info \
              /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.*

RUN groupadd --gid 10001 caderneta \
    && useradd --uid 10001 --gid 10001 --home-dir /app --shell /usr/sbin/nologin caderneta

WORKDIR /app

COPY --from=builder --chown=10001:10001 /app/.venv /app/.venv
COPY --chown=10001:10001 alembic.ini ./
COPY --chown=10001:10001 src ./src
COPY --chown=10001:10001 scripts/entrypoint.sh /usr/local/bin/entrypoint.sh

# /data is created with the right owner here so that the named volume inherits
# the permission - otherwise the non-root container cannot write to SQLite.
RUN chmod +x /usr/local/bin/entrypoint.sh \
    && mkdir -p /data \
    && chown 10001:10001 /data

USER 10001:10001

VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3).status==200 else 1)"

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["python", "-m", "caderneta.bot"]
