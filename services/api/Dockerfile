# Lifeline API and worker image. Owned by W8.
# Used by docker-compose.yml for both the `api` and `worker` services.
# Two stages: `build` resolves dependencies with uv; `runtime` holds only the venv and source.

# ---- build stage ----
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_NO_CACHE=1
WORKDIR /app

# Dependencies first, so source edits do not invalidate this layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Project source (filtered by .dockerignore), then install the project itself.
COPY . .
RUN uv sync --frozen --no-dev

# ---- runtime stage ----
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app
WORKDIR /app
# Same path as the build stage: the venv holds an editable link to /app.
COPY --from=build --chown=app:app /app /app
USER app
EXPOSE 8000
# One image serves both services. ROLE=worker runs the refresh worker; anything else runs the API on $PORT
# (default 8000) behind a proxy (Railway). docker-compose sets `command` per service, so local runs ignore ROLE.
# Demo seed: `python -m seed.load` (see `make demo-seed`).
CMD ["sh","-c","if [ \"$ROLE\" = worker ]; then exec python -m lifeline_data.worker; else exec uvicorn lifeline_api.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'; fi"]
