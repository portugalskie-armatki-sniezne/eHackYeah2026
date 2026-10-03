FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.22 /uv /bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UVICORN_PORT=8000 UPLOAD_DIR=/app/uploads PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY apps/notify/pyproject.toml apps/notify/uv.lock ./
RUN uv sync --locked --no-dev --no-cache
COPY apps/notify/app app
COPY apps/notify/templates templates
RUN mkdir uploads && chown 65534:65534 uploads
USER 65534:65534
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0"]
