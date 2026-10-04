FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.22 /uv /bin/uv

# the photo volume and the mounted service-account key match docker-compose.app.yaml;
# GOOGLE_CLOUD_PROJECT has no safe default and comes from the environment
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UVICORN_PORT=8000 PATH="/app/.venv/bin:$PATH" \
    UPLOAD_DIR=/app/uploads GOOGLE_CLOUD_LOCATION=global \
    GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/gemini-service-account.json
WORKDIR /app
COPY apps/gemini/pyproject.toml apps/gemini/uv.lock ./
RUN uv sync --locked --no-dev --no-cache
COPY apps/gemini/app app
USER 65534:65534
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0"]
