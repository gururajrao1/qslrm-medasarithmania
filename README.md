# QSLRM / MedasArithmania

Hypothesis triage & decision engine for translational ADR risk.
**Not** automated causality. **Not** an Argus/Vault replacement.

Join grain: `drug ↔ target/gene ↔ MedDRA PT` (never patient UUID).

## What it does

Ranks kinase drug–ADR pairs with fused multi-omic + FAERS signals, then surfaces decisions:

- Dose review · genetic filter / protocol exclusion · rising-signal velocity · DSUR draft

## Stack

| Layer | Tech |
|-------|------|
| API + UI | FastAPI + static `web/` |
| DB | SQLite (free Render bake-in) / optional Postgres |
| Engines | Python signals + omic fusion (`omic_engine` Julia-compatible math) |

Wired sources: openFDA FAERS, ChEMBL, Open Targets, ClinVar, LINCS fixtures, CT.gov, RxNorm/CYP.

## Local (SQLite)

```bash
cp .env.example .env
# set DATABASE_URL=sqlite:///./data/processed/qslrm.db

python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -e ".[dev]"

python -m scripts.bootstrap_db
python -m scripts.seed_db
python -m scripts.run_phase1 --offline-dir tests/fixtures/phase1
python -m scripts.run_phase2
python -m scripts.run_phase3
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

## Deploy (free — Render + baked SQLite)

No paid Postgres. The release DB snapshot (`data/processed/qslrm.release.db`) is copied into the image so fused pairs are preserved.

```bash
# 1) Refresh snapshot from backup/local (optional)
python -m scripts.build_release_db

# 2) Push to GitHub, then one-click Render free web service:
#    https://render.com/deploy?repo=https://github.com/gururajrao1/qslrm-medasarithmania
# Or: New → Blueprint → select this repo (uses render.yaml)
```

Migrated snapshot preserves **~1499 fused pairs** / 27 drugs (not just the UI “~200” sample). Railway/Postgres not required.

Local Docker (same image):

```bash
docker build -t qslrm .
docker run --rm -p 8000:8000 qslrm
```

## Deployable (Docker Compose — optional Postgres)

Builds API image, starts Postgres, bootstraps schema, loads offline fixtures, serves `:8000`.

```bash
docker compose up --build
```

Skip re-ingest on restart by setting `QSLRM_SEED_PIPELINE=0` once data exists.

## Tests

```bash
pytest -q
```

## Product claim

> Rank attributable drug–ADR hypotheses for triage — dose / off-target / transcriptomic / genetic — with audit-ready exports. Disproportionality ≠ causality.
