# QSLRM (MedasArithmania)

Hypothesis triage engine for translational adverse drug reaction (ADR) risk. It ranks drug–target–MedDRA pairs using public pharmacovigilance and multi-omic signals to support dose review, genetic filtering, and signal velocity triage.

> Disproportionality is not causality. This is not a replacement for Argus, Vault, or any regulated PV system.

## Features

- Fused risk scores for drug ↔ gene/target ↔ MedDRA PT pairs
- Ingest from openFDA FAERS, ClinicalTrials.gov, ChEMBL, Open Targets, ClinVar, and related fixtures
- FastAPI backend with a simple web UI
- SQLite by default; Postgres optional
- Streaming event ledger for live ingest ticks

## Requirements

- Python 3.11+
- (Optional) Docker / Docker Compose

## Quick start

```bash
git clone https://github.com/gururajrao1/qslrm-medasarithmania.git
cd qslrm-medasarithmania

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -e ".[dev]"
cp .env.example .env
```

Set `DATABASE_URL` in `.env`:

```env
DATABASE_URL=sqlite:///./data/processed/qslrm.db
MODEL_VERSION=qslrm-v1.0.0
```

Bootstrap, seed, and run the offline pipeline:

```bash
python -m scripts.bootstrap_db
python -m scripts.seed_db
python -m scripts.run_phase1 --offline-dir tests/fixtures/phase1
python -m scripts.run_phase2
python -m scripts.run_phase3

uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | SQLAlchemy URL (`sqlite:///...` or Postgres) | required |
| `MODEL_VERSION` | Model label shown in UI/API | `qslrm-v1.0.0` |
| `QSLRM_BOOTSTRAP` | Create schema + seed on container start | `1` |
| `QSLRM_SEED_PIPELINE` | Run phase1–3 ingest on start | `1` |

## Project layout

```
api/            FastAPI app
web/            Static UI
qslrm_erd/      Models, settings, DB helpers
ingest/         Source loaders (FAERS, CT.gov, …)
signals/        Signal stats
fusion/         Score fusion
omic_engine/    Multi-omic scoring
stream/         Event ledger / WebSocket
scripts/        CLI entrypoints
tests/          Pytest + fixtures
```

## Docker

Build and run with the baked release SQLite snapshot:

```bash
docker build -t qslrm .
docker run --rm -p 8000:8000 qslrm
```

Or with Compose (optional Postgres):

```bash
docker compose up --build
```

## Deploy (Render)

Free web service via Docker + baked SQLite (`render.yaml`). No paid database required.

[Deploy to Render](https://render.com/deploy?repo=https://github.com/gururajrao1/qslrm-medasarithmania)

To refresh the release snapshot before deploy:

```bash
python -m scripts.build_release_db
```

## Tests

```bash
pytest -q
```

## License

MIT
