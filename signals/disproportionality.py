"""Pharmacovigilance disproportionality metrics — PRR, ROR, Dirichlet/EBGM-style shrink.

These are signal generators for hypothesis triage, not causality.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Contingency:
  """2×2 drug × event counts.

  n11: drug+event
  n10: drug+other events
  n01: other drugs+event
  n00: other drugs+other events
  """

  n11: int
  n10: int
  n01: int
  n00: int

  @property
  def n1_(self) -> int:
    return self.n11 + self.n10

  @property
  def n_1(self) -> int:
    return self.n11 + self.n01

  @property
  def n__(self) -> int:
    return self.n11 + self.n10 + self.n01 + self.n00


@dataclass(frozen=True)
class SignalMetrics:
  prr: float
  ror: float
  ror_ci_low: float
  ror_ci_high: float
  ic: float
  ebgm: float
  n11: int
  n1_: int
  n_1: int
  n__: int


def _safe_div(a: float, b: float) -> float:
  if b == 0:
    return float("nan")
  return a / b


def proportional_reporting_ratio(c: Contingency) -> float:
  # PRR = (n11/n1_) / (n01/n0_) where n0_ = n01+n00
  n0_ = c.n01 + c.n00
  return _safe_div(c.n11 / c.n1_ if c.n1_ else float("nan"), c.n01 / n0_ if n0_ else float("nan"))


def reporting_odds_ratio(c: Contingency) -> tuple[float, float, float]:
  # ROR = (n11/n10) / (n01/n00) = n11*n00 / (n10*n01)
  if min(c.n11, c.n10, c.n01, c.n00) == 0:
    # Haldane-Anscombe continuity correction for CI stability
    a, b, cc, d = c.n11 + 0.5, c.n10 + 0.5, c.n01 + 0.5, c.n00 + 0.5
  else:
    a, b, cc, d = float(c.n11), float(c.n10), float(c.n01), float(c.n00)
  ror = (a * d) / (b * cc)
  se = float(np.sqrt(1 / a + 1 / b + 1 / cc + 1 / d))
  log_ror = float(np.log(ror))
  return ror, float(np.exp(log_ror - 1.96 * se)), float(np.exp(log_ror + 1.96 * se))


def information_component(c: Contingency, alpha: float = 0.5) -> float:
  """Bate IC with Dirichlet-style prior (alpha on expected count)."""
  expected = _safe_div(c.n1_ * c.n_1, c.n__)
  if np.isnan(expected):
    return float("nan")
  return float(np.log2((c.n11 + alpha) / (expected + alpha)))


def ebgm_shrink(c: Contingency, alpha1: float = 0.5, alpha2: float = 0.5) -> float:
  """Simple empirical-Bayes geometric mean style shrink toward null (=1).

  For rare cells (n11 < 3) this pulls PRR toward 1 to reduce noise.
  """
  prr = proportional_reporting_ratio(c)
  if np.isnan(prr):
    return float("nan")
  # posterior weight grows with n11
  w = (c.n11 + alpha1) / (c.n11 + alpha1 + alpha2)
  return float(np.exp(w * np.log(max(prr, 1e-12))))


def compute_signals(c: Contingency, min_n: int = 3) -> SignalMetrics | None:
  """Return metrics, or None if below support threshold after noting rare-event shrink still runs."""
  if c.n11 < 1:
    return None
  prr = proportional_reporting_ratio(c)
  ror, lo, hi = reporting_odds_ratio(c)
  ic = information_component(c)
  ebgm = ebgm_shrink(c)
  if c.n11 < min_n:
    # still return shrunk metrics for triage visibility
    pass
  return SignalMetrics(
    prr=prr,
    ror=ror,
    ror_ci_low=lo,
    ror_ci_high=hi,
    ic=ic,
    ebgm=ebgm,
    n11=c.n11,
    n1_=c.n1_,
    n_1=c.n_1,
    n__=c.n__,
  )
