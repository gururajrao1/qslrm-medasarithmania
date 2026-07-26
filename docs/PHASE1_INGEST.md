# Phase 1 — ETL & Ingestion

## Scope

Kinase-inhibitor MVP only. Never ingest full FAERS.

| Step | Source | Tables |
|------|--------|--------|
| Targetome | ChEMBL REST mechanisms + activities | `target`, `drug_target`, crosswalks |
| Pathways | Open Targets GraphQL | `pathway`, `pathway_target` |
| Variants | ClinVar via NCBI E-utilities | `variant` |
| PV | openFDA drug/event (per-drug slice) | `ae_term`, `pv_case`, `pv_drug_event` |

## Commands

```bash
# Schema + Phase 0 seed
python -m scripts.bootstrap_db
python -m scripts.seed_db
python -m scripts.phase0_check

# Phase 1 live (needs network)
python -m scripts.run_phase1

# Phase 1 offline (fixtures / CI)
python -m scripts.run_phase1 --offline-dir tests/fixtures/phase1

# Single step
python -m scripts.run_phase1 --steps faers
```

## QC

`data/processed/qc_report.json` is written after Phase 1.

- `phase0_pass`: ontology spine + kinase seed complete
- `phase1_pass`: FAERS events + variants + pathways + drug_target coverage

## Raw snapshots

Live FAERS pulls are written under `data/raw/faers/{drug}.json`.
