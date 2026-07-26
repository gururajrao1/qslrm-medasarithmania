"""Run Phase 1 ingest pipeline (live APIs or offline fixtures)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy.orm import Session

from ingest.pipeline import run_phase1
from ingest.qc import build_qc_report
from qslrm_erd.db import get_engine


def main() -> None:
  parser = argparse.ArgumentParser(description="QSLRM Phase 1 ingest")
  parser.add_argument(
    "--steps",
    default=(
      "chembl,opentargets,clinvar,faers,lincs,ctgov,literature,sider,onsides,"
      "opentargets_pv,openfda_spl,orange_book,bindingdb,tox21,depmap,eudravigilance,"
      "meddra_codes,meddra_hierarchy,ictrp_ctri,synthea"
    ),
    help="Comma-separated ingest steps",
  )
  parser.add_argument(
    "--offline-dir",
    type=Path,
    default=None,
    help="Load fixtures from directory instead of live APIs",
  )
  parser.add_argument("--json", action="store_true")
  args = parser.parse_args()

  steps = [s.strip() for s in args.steps.split(",") if s.strip()]
  engine = get_engine()
  with Session(engine) as session:
    summary = run_phase1(session, steps=steps, offline_dir=args.offline_dir)
    qc = build_qc_report(session)

  out = {"summary": summary, "phase0_pass": qc["phase0_pass"], "phase1_pass": qc["phase1_pass"]}
  if args.json:
    print(json.dumps(out, indent=2, default=str))
  else:
    print(json.dumps(summary, indent=2, default=str))
    print("phase0_pass=", qc["phase0_pass"], "phase1_pass=", qc["phase1_pass"])

  raise SystemExit(0 if qc["phase1_pass"] else 2)


if __name__ == "__main__":
  main()
