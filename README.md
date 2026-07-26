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
| DB | Postgres 16 (prod) / SQLite (local) |
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
# 1) Refresh snapshot from your local DB (optional)
copy data\processed\qslrm.db data\processed\qslrm.release.db

# 2) Push to GitHub, then one-click Render free web service
#    https://render.com/deploy
# Or: New → Blueprint → select this repo (render.yaml)
```

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
