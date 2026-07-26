"""Phase 0 exit-criteria checker."""

from __future__ import annotations

import argparse
import json
import sys

from sqlalchemy.orm import Session

from ingest.qc import build_qc_report
from qslrm_erd.db import get_engine


def main() -> None:
  parser = argparse.ArgumentParser(description="Verify Phase 0 completion")
  parser.add_argument("--json", action="store_true", help="Print full QC JSON")
  args = parser.parse_args()

  engine = get_engine()
  with Session(engine) as session:
    report = build_qc_report(session)

  if args.json:
    print(json.dumps(report, indent=2))
  else:
    print("Phase 0 pass:" if report["phase0_pass"] else "Phase 0 FAIL:")
    for k, v in report["checks"].items():
      if k.startswith("phase1"):
        continue
      print(f"  [{ 'OK' if v else 'X' }] {k}")
    print("counts:", report["counts"])

  raise SystemExit(0 if report["phase0_pass"] else 1)


if __name__ == "__main__":
  main()
