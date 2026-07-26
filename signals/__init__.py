"""signals/ — Python PV engine (PRR/ROR/IC/EBGM)."""

from signals.contingency_builder import build_contingency_map
from signals.disproportionality import Contingency, SignalMetrics, compute_signals
from signals.runner import run_signal_detection

__all__ = [
  "Contingency",
  "SignalMetrics",
  "compute_signals",
  "build_contingency_map",
  "run_signal_detection",
]
