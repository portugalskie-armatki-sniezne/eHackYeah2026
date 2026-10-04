FROM python:3.14-slim AS dependencies
COPY --from=ghcr.io/astral-sh/uv:0.12.22 /uv /bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# the build context is the repository root, like for the web image
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --locked --no-dev --no-cache --extra inference \
    && python -c "import torch; assert torch.version.cuda is None, 'CPU-only PyTorch is required'"

FROM dependencies AS models
# application changes reuse the pinned model download layer
COPY apps/api/app/inference/__init__.py apps/api/app/inference/models.py apps/api/app/inference/download.py app/inference/
RUN python -m app.inference.download

FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH" \
    LAYA_MODEL_PATH=/app/models/laya-vision TRANSLATION_MODEL_PATH=/app/models/opus-mt-pl-en \
    LAYA_DEVICE=cpu INFERENCE_REQUIRED=true HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HOME=/tmp/huggingface
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=dependencies /app/.venv .venv
COPY --from=models /app/models models
COPY apps/api/app app
# the default UPLOAD_DIR for report photos must be writable by the unprivileged user
RUN mkdir uploads && chown 65534:65534 uploads
USER 65534:65534
# fail the image build if either model cannot perform a real prediction offline
RUN --network=none python -m app.inference.warmup
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
