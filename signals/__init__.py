"""signals/ — Python PV engine (PRR/ROR/IC/EBGM)."""

from signals.contingency_builder import build_contingency_map
from signals.disproportionality import (
  Contingency,
  SignalMetrics,
  compute_signals,
  ebgm_mgps,
  ic_credible_low,
  prr_chi_square,
  prr_with_ci,
  triage_decision,
  triage_masked,
)
from signals.runner import run_signal_detection

__all__ = [
  "Contingency",
  "SignalMetrics",
  "build_contingency_map",
  "compute_signals",
  "ebgm_mgps",
  "ic_credible_low",
  "prr_chi_square",
  "prr_with_ci",
  "run_signal_detection",
  "triage_decision",
  "triage_masked",
]
