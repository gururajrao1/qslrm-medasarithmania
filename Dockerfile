FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    MODEL_VERSION=qslrm-v1.0.0 \
    QSLRM_BOOTSTRAP=1 \
    QSLRM_SEED_PIPELINE=1 \
    DATABASE_URL=sqlite:///./data/processed/qslrm.db

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md alembic.ini ./
COPY qslrm_erd ./qslrm_erd
COPY ingest ./ingest
COPY signals ./signals
COPY fusion ./fusion
COPY omic_engine ./omic_engine
COPY stream ./stream
COPY api ./api
COPY web ./web
COPY scripts ./scripts
COPY tests/fixtures/phase1 ./tests/fixtures/phase1

RUN pip install --no-cache-dir -e . \
    && mkdir -p /app/data/processed /app/data/raw

# 8000 local/Render; Hugging Face Spaces sets PORT=7860
EXPOSE 8000 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=5 \
  CMD-SHELL curl -fsS http://127.0.0.1:$${PORT:-8000}/health || exit 1

CMD ["python", "-m", "scripts.entrypoint"]
