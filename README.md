---
title: QSLRM MedasArithmania
emoji: 🧬
colorFrom: teal
colorTo: gray
sdk: docker
pinned: false
app_port: 7860
---

# QSLRM / MedasArithmania

Hypothesis triage & decision engine for translational ADR risk.
**Not** automated causality. **Not** an Argus/Vault replacement.

Join grain: `drug ↔ target/gene ↔ MedDRA PT` (never patient UUID).

## Free deploy (recommended)

Uses **SQLite** (no paid database). Seeds itself on first boot from offline fixtures.

### Option A — Render Free

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/gururajrao1/qslrm-medasarithmania)

Or: Render Dashboard → **New** → **Blueprint** → select this repo (`render.yaml`).

> Free web services **sleep after ~15 min** idle (cold start ~30–60s). Fine for demos.

### Option B — Hugging Face Spaces (Docker, free CPU)

This README is Space-ready (`sdk: docker`, port `7860`).  
Create a Space from this GitHub repo, or duplicate as a Docker Space — set `PORT=7860`.

### Option C — Local (free forever)

```bash
# SQLite — no Postgres required
set DATABASE_URL=sqlite:///./data/processed/qslrm.db
python -m scripts.bootstrap_db
python -m scripts.seed_db
python -m scripts.run_phase1 --offline-dir tests/fixtures/phase1
python -m scripts.run_phase2
python -m scripts.run_phase3
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

## Stack

| Layer | Tech |
|-------|------|
| API + UI | FastAPI + static `web/` |
| DB | **SQLite (free default)** / Postgres optional |
| Engines | Python signals + omic fusion |

## Tests

```bash
pytest -q
```

## Product claim

> Rank attributable drug–ADR hypotheses for triage — dose / off-target / transcriptomic / genetic — with audit-ready exports. Disproportionality ≠ causality.
