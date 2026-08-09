# syntax=docker/dockerfile:1

# ---- frontend build ----
FROM node:22-slim AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json frontend/
RUN cd frontend && npm ci
COPY frontend frontend/
RUN cd frontend && npm run build
# vite.config.ts outDir '../backend/static' lands the build at /app/backend/static

# ---- python runtime ----
FROM python:3.12-slim AS runtime
RUN pip install --no-cache-dir uv

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend/app ./app
COPY --from=frontend-build /app/backend/static ./static

# /data is the mounted volume (see docker-compose.yml); this is packaging for
# a single local container, not deployment — see PLAN.md §2a.
ENV PULSEDESK_DB_PATH=/data/pulsedesk.db
EXPOSE 8000
VOLUME ["/data"]

# Not `uv run`: it re-checks the project's full sync state (dev group
# included) on every invocation and reaches for the network to fix any
# mismatch against --no-dev above, breaking the offline guarantee. The venv
# is already fully built — call its uvicorn directly.
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
