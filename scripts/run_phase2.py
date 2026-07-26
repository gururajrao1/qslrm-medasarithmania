"""Run Phase 2 dual engines (signals + omic)."""

from __future__ import annotations

import argparse
import json

from sqlalchemy.orm import Session

from ingest.qc import build_qc_report
from omic_engine.pipeline import run_phase2
from qslrm_erd.db import get_engine


def main() -> None:
  parser = argparse.ArgumentParser(description="QSLRM Phase 2 — signals + omic engines")
  parser.add_argument(
    "--steps",
    default="signals,velocity,demographics,nlp,omic",
    help="Comma-separated: signals,velocity,demographics,nlp,omic",
  )
  parser.add_argument("--julia", action="store_true", help="Prefer Julia OmicEngine if available")
  parser.add_argument("--json", action="store_true")
  args = parser.parse_args()

  steps = [s.strip() for s in args.steps.split(",") if s.strip()]
  engine = get_engine()
  with Session(engine) as session:
    summary = run_phase2(session, steps=steps, prefer_julia=args.julia)
    qc = build_qc_report(session)

  out = {"summary": summary, "phase2_pass": qc.get("phase2_pass"), "phase1_pass": qc.get("phase1_pass")}
  if args.json:
    print(json.dumps(out, indent=2, default=str))
  else:
    print(json.dumps(summary, indent=2, default=str))
    print("phase2_pass=", qc.get("phase2_pass"))

  raise SystemExit(0 if qc.get("phase2_pass") else 2)


if __name__ == "__main__":
  main()
