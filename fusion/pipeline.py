"""Phase 3 orchestration — fusion, DDI, protocol exclusions."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from fusion.ddi import compute_ddi_risks
from fusion.protocol import generate_protocol_exclusions
from fusion.runner import run_fusion
from ingest.qc import write_qc_report


def run_phase3(session: Session) -> dict[str, Any]:
  summary: dict[str, Any] = {"steps": {}}
  summary["steps"]["fusion"] = run_fusion(session)
  summary["steps"]["ddi"] = compute_ddi_risks(session)
  summary["steps"]["protocol"] = generate_protocol_exclusions(session)
  summary["qc_report"] = str(write_qc_report(session))
  return summary
