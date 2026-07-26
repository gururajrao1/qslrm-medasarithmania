# Phase 3 — Fusion, attribution, UI

## Goal

Fuse PV + omic + dose into `fused_score` (0–100), write dose / off-target / genetics attributions, serve a **non-Streamlit** triage UI.

## Math

$$
\text{Fused}=100\cdot\sigma(w_1 z_{signal}+w_2 z_{omic}+w_3 z_{dose})
$$

Attributions normalize to ~1 using dose mass + omic split (`S_off` vs `S_gen`) + signal mass folded into the same split.

## UI

Stitch MCP screen generation failed on this host (`screens` undefined), so the product UI is a custom **ink/teal** static app:

- `web/index.html` + `web/static/*`
- Served by FastAPI at `/`
- Data from `/v1/risk-scores`, audit via `/v1/audit?format=json|csv`

## Commands

```bash
python -m scripts.run_phase3
uvicorn api.main:app --reload
# open http://127.0.0.1:8000/
```

## Exit (`phase3_pass`)

- `risk_score.fused_score` populated
- attribution columns populated
- Phase 2 still passing
