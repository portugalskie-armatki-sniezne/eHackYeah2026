FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.22 /uv /bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
WORKDIR /app
# the build context is the repository root, like for the web image
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --locked --no-dev --no-cache
COPY apps/api/app app
# the default UPLOAD_DIR for report photos must be writable by the unprivileged user
RUN mkdir uploads && chown 65534:65534 uploads
USER 65534:65534
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
