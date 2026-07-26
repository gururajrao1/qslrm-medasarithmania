"""Phase 2 orchestration — signals, velocity, demographics, NLP, omic."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ingest.qc import write_qc_report
from omic_engine.runner import run_omic_scoring
from signals.demographics import compute_demographic_signals
from signals.nlp_narratives import run_narrative_nlp
from signals.runner import run_signal_detection, seed_period_signals_for_velocity
from signals.velocity import compute_signal_velocity


def run_phase2(
  session: Session,
  *,
  steps: list[str] | None = None,
  prefer_julia: bool = False,
) -> dict[str, Any]:
  wanted = steps or ["signals", "velocity", "demographics", "nlp", "omic"]
  summary: dict[str, Any] = {"steps": {}}
  if "signals" in wanted:
    summary["steps"]["signals"] = run_signal_detection(session)
    summary["steps"]["period_signals"] = seed_period_signals_for_velocity(session)
  if "velocity" in wanted:
    summary["steps"]["velocity"] = compute_signal_velocity(session)
  if "demographics" in wanted:
    summary["steps"]["demographics"] = compute_demographic_signals(session)
  if "nlp" in wanted:
    summary["steps"]["nlp"] = run_narrative_nlp(session)
  if "omic" in wanted:
    summary["steps"]["omic"] = run_omic_scoring(session, prefer_julia=prefer_julia)
  summary["qc_report"] = str(write_qc_report(session))
  return summary
