# syntax=docker/dockerfile:1.7

# ---- 前端构建 ----
FROM node:20-bookworm-slim AS web-builder
WORKDIR /repo
COPY package.json package-lock.json* ./
COPY apps/web/package.json ./apps/web/package.json
COPY packages/ ./packages/
RUN npm ci --workspaces=false --include-workspace-root || npm install
COPY apps/web ./apps/web
COPY packages ./packages
RUN npm run build --workspace @mock-interview/web

# ---- 后端依赖 ----
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS api-builder
WORKDIR /repo
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
COPY apps/api/requirements.txt ./apps/api/requirements.txt
RUN uv venv /opt/venv \
    && uv pip install --python /opt/venv/bin/python -r apps/api/requirements.txt

# ---- 运行时 ----
FROM python:3.13-slim-bookworm AS runtime
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=api-builder /opt/venv /opt/venv
COPY apps/api/app ./apps/api/app
COPY --from=web-builder /repo/apps/web/dist ./apps/web/dist
EXPOSE 8000
CMD ["uvicorn", "apps.api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
