FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.22 /uv /bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-cache
COPY import_local_government_offices.py import_service_entities.py import_reference_data.py collect_service_entities.py ./
COPY populate_mock_data.py mock_data.py ./
COPY mock_photos mock_photos
USER 65534:65534
ENTRYPOINT ["python", "/app/import_reference_data.py"]
