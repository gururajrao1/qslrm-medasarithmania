"""Run Phase 3 fusion + attribution."""

from __future__ import annotations

import argparse
import json

from sqlalchemy.orm import Session

from fusion.pipeline import run_phase3
from ingest.qc import build_qc_report
from qslrm_erd.db import get_engine


def main() -> None:
  parser = argparse.ArgumentParser(description="QSLRM Phase 3 — fusion + attribution")
  parser.add_argument("--json", action="store_true")
  args = parser.parse_args()

  engine = get_engine()
  with Session(engine) as session:
    summary = run_phase3(session)
    qc = build_qc_report(session)

  out = {"summary": summary, "phase3_pass": qc.get("phase3_pass"), "phase2_pass": qc.get("phase2_pass")}
  if args.json:
    print(json.dumps(out, indent=2, default=str))
  else:
    print(json.dumps(summary, indent=2, default=str))
    print("phase3_pass=", qc.get("phase3_pass"))

  raise SystemExit(0 if qc.get("phase3_pass") else 2)


if __name__ == "__main__":
  main()
