"""Phase 4 — BBW enrichment check: labeled pairs should land in top fused ranks."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from qslrm_erd.db import get_engine, reset_engine
from qslrm_erd.models import GroundTruthLabel, RiskScore
from qslrm_erd.settings import get_settings


def validate_bbw_enrichment(
  session: Session,
  *,
  top_pct: float = 0.20,
  min_enrichment: float = 0.50,
  label_types: tuple[str, ...] = ("black_box",),
) -> dict:
  """Require a minimum fraction of BBW pairs inside the top fused ranks.

  For small MVP fixture corpora, top_pct defaults to 20% (prompt target is 5% at scale).
  """
  settings = get_settings()
  ranks = session.scalars(
    select(RiskScore)
    .where(
      RiskScore.model_version == settings.model_version,
      RiskScore.fused_score.is_not(None),
    )
    .order_by(RiskScore.fused_score.desc())
  ).all()
  if not ranks:
    return {"phase4_pass": False, "reason": "no fused scores"}

  n = len(ranks)
  cutoff = max(1, int(round(n * top_pct)))
  top_keys = {(r.drug_id, r.ae_term_id) for r in ranks[:cutoff]}
  labels = session.scalars(
    select(GroundTruthLabel).where(GroundTruthLabel.label_type.in_(label_types))
  ).all()
  label_keys = {(g.drug_id, g.ae_term_id) for g in labels}
  if not label_keys:
    return {
      "phase4_pass": False,
      "reason": "no black_box ground-truth labels",
      "n_ranked": n,
      "model_version": settings.model_version,
    }
  hit = label_keys & top_keys
  enrichment = len(hit) / len(label_keys)
  missing = sorted(label_keys - top_keys)
  ok = enrichment >= min_enrichment and n >= 1
  return {
    "phase4_pass": ok,
    "n_ranked": n,
    "top_pct": top_pct,
    "top_cutoff": cutoff,
    "min_enrichment": min_enrichment,
    "n_labels": len(label_keys),
    "labels_in_top": len(hit),
    "enrichment": enrichment,
    "missing_from_top": [{"drug_id": d, "ae_term_id": a} for d, a in missing],
    "model_version": settings.model_version,
  }


def main() -> None:
  reset_engine()
  engine = get_engine()
  with Session(engine) as session:
    report = validate_bbw_enrichment(session)
  out = Path(get_settings().processed_data_dir) / "phase4_bbw.json"
  out.parent.mkdir(parents=True, exist_ok=True)
  out.write_text(json.dumps(report, indent=2), encoding="utf-8")
  print(json.dumps(report, indent=2))
  raise SystemExit(0 if report.get("phase4_pass") else 2)


if __name__ == "__main__":
  main()
