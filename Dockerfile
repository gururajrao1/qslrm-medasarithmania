# Free-tier deploy (no paid Postgres): bake release SQLite into image
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    MODEL_VERSION=qslrm-v1.0.0 \
    DATABASE_URL=sqlite:////app/data/processed/qslrm.db \
    QSLRM_BOOTSTRAP=0 \
    QSLRM_SEED_PIPELINE=0

RUN apt-get update && apt-get install -y --no-install-recommends \
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

# Migrated production snapshot (fused pairs preserved)
COPY data/processed/qslrm.release.db /app/data/processed/qslrm.db

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=5 \
  CMD curl -fsS http://127.0.0.1:${PORT}/health || exit 1

CMD ["python", "-m", "scripts.entrypoint"]
