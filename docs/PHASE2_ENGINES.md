# Phase 2 — Dual computation engines

## Goal

Wire ingested FAERS + targetome into:

1. **signals/** — 2×2 contingencies → PRR / ROR / IC / EBGM → `signal_stat`
2. **omic_engine/** — `S_off`, `S_path`, `S_gen` → `S_omic` → `omic_score`

Also seeds PV + omic fields on `risk_score` (fusion left for Phase 3).

## Formulas

$$
S_{omic}=\sigma(\alpha S_{off}+\beta S_{path}+\gamma S_{gen})
$$

PRR/ROR from classic 2×2 on `pv_drug_event` link rows. Rare cells (`n11 < 3`) still emit metrics with EBGM shrinkage.

## Commands

```bash
# After Phase 0+1
python -m scripts.run_phase2

# Signals only / omic only
python -m scripts.run_phase2 --steps signals
python -m scripts.run_phase2 --steps omic

# Prefer Julia if installed (falls back to Python)
python -m scripts.run_phase2 --julia
```

## Exit criteria (`phase2_pass`)

- `signal_stat` rows > 0
- `omic_score` rows > 0
- `risk_score` seeded with PRR/ROR and/or `omic_risk`
- Phase 1 still passing
