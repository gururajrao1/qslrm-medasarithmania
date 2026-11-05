"""Pharmacovigilance disproportionality metrics — PRR, ROR, IC, EBGM.

Signal generators for hypothesis triage, not causality. Point estimates ship
with uncertainty (PRR chi-square/CI, ROR CI, IC025, EB05/EB95) and a triage
mask so under-supported cells are flagged watchlist instead of ranked.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.special import digamma
from scipy.stats import gamma


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
  prr_chi2: float = field(default=float("nan"))
  prr_ci_low: float = field(default=float("nan"))
  prr_ci_high: float = field(default=float("nan"))
  ic025: float = field(default=float("nan"))
  eb05: float = field(default=float("nan"))
  eb95: float = field(default=float("nan"))
  watchlist: bool = field(default=False)


def _safe_div(a: float, b: float) -> float:
  if b == 0:
    return float("nan")
  return a / b


def _finite(x: float) -> bool:
  return x is not None and np.isfinite(x)


def proportional_reporting_ratio(c: Contingency) -> float:
  # PRR = (n11/n1_) / (n01/n0_) where n0_ = n01+n00
  n0_ = c.n01 + c.n00
  return _safe_div(c.n11 / c.n1_ if c.n1_ else float("nan"), c.n01 / n0_ if n0_ else float("nan"))


def prr_with_ci(c: Contingency) -> tuple[float, float, float]:
  """PRR with Wald 95% CI on the log scale; NaN bounds when cells are empty."""
  prr = proportional_reporting_ratio(c)
  n0_ = c.n01 + c.n00
  if not _finite(prr) or prr <= 0 or min(c.n11, c.n1_, c.n01, n0_) <= 0:
    return prr, float("nan"), float("nan")
  se = float(np.sqrt(1 / c.n11 - 1 / c.n1_ + 1 / c.n01 - 1 / n0_))
  if not _finite(se):
    return prr, float("nan"), float("nan")
  log_prr = float(np.log(prr))
  return prr, float(np.exp(log_prr - 1.96 * se)), float(np.exp(log_prr + 1.96 * se))


def prr_chi_square(c: Contingency) -> float:
  """Pearson chi-square (1 df, no Yates correction) for the 2×2 table."""
  n0_ = c.n01 + c.n00
  n_0 = c.n10 + c.n00
  denom = c.n1_ * n0_ * c.n_1 * n_0
  if denom <= 0 or c.n__ <= 0:
    return float("nan")
  num = c.n__ * (c.n11 * c.n00 - c.n10 * c.n01) ** 2
  return float(num / denom)


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


def ic_credible_low(c: Contingency, alpha: float = 0.5) -> float:
  """IC025-style lower credibility bound (Noren shrinkage approximation)."""
  ic = information_component(c, alpha=alpha)
  if not _finite(ic):
    return float("nan")
  n = c.n11 + 0.5
  return float(ic - 3.3 * n**-0.5 - 2.0 * n**-1.5)


def ebgm_shrink(c: Contingency, alpha1: float = 0.5, alpha2: float = 0.5) -> float:
  """Legacy shrink toward null (=1); prefer ebgm_mgps for new code."""
  prr = proportional_reporting_ratio(c)
  if np.isnan(prr):
    return float("nan")
  w = (c.n11 + alpha1) / (c.n11 + alpha1 + alpha2)
  return float(np.exp(w * np.log(max(prr, 1e-12))))


def ebgm_mgps(c: Contingency, alpha: float = 1.0) -> tuple[float, float, float]:
  """Gamma-Poisson (MGPS-lite) posterior: EBGM + EB05/EB95 credibility bounds.

  Posterior lambda ~ Gamma(n11 + alpha, E + alpha) with E the expected count
  under independence. EBGM = exp(E[log lambda]).
  """
  expected = _safe_div(c.n1_ * c.n_1, c.n__)
  if not _finite(expected) or expected <= 0:
    return float("nan"), float("nan"), float("nan")
  shape = c.n11 + alpha
  rate = expected + alpha
  ebgm = float(np.exp(digamma(shape) - np.log(rate)))
  eb05 = float(gamma.ppf(0.05, shape, scale=1.0 / rate))
  eb95 = float(gamma.ppf(0.95, shape, scale=1.0 / rate))
  return ebgm, eb05, eb95


def triage_masked(m: SignalMetrics, *, min_n: int = 3) -> bool:
  """True when a pair meets the triage bar; else it is watchlist-only."""
  if m.n11 < min_n:
    return False
  prr_rule = _finite(m.prr) and m.prr >= 2.0 and _finite(m.prr_chi2) and m.prr_chi2 >= 4.0
  ror_rule = _finite(m.ror_ci_low) and m.ror_ci_low > 1.0
  ic_rule = _finite(m.ic025) and m.ic025 > 0.0
  eb_rule = _finite(m.eb05) and m.eb05 >= 2.0
  return bool(prr_rule or ror_rule or ic_rule or eb_rule)


def triage_decision(n11: int, n1_: int, n_1: int, n__: int) -> tuple[bool, bool, SignalMetrics | None]:
  """(masked, watchlist, metrics) from raw 2×2 margins; metrics None if n11 < 1."""
  m = compute_signals(Contingency(n11=n11, n10=n1_ - n11, n01=n_1 - n11, n00=n__ - n1_ - n_1 + n11))
  if m is None:
    return False, True, None
  masked = triage_masked(m)
  return masked, not masked, m


def compute_signals(c: Contingency, min_n: int = 3) -> SignalMetrics | None:
  """Return metrics (never None for n11 >= 1); sub-threshold pairs are watchlist."""
  if c.n11 < 1:
    return None
  prr = proportional_reporting_ratio(c)
  _prr, prr_lo, prr_hi = prr_with_ci(c)
  chi2 = prr_chi_square(c)
  ror, lo, hi = reporting_odds_ratio(c)
  ic = information_component(c)
  ic025 = ic_credible_low(c)
  ebgm, eb05, eb95 = ebgm_mgps(c)
  tentative = SignalMetrics(
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
    prr_chi2=chi2,
    prr_ci_low=prr_lo,
    prr_ci_high=prr_hi,
    ic025=ic025,
    eb05=eb05,
    eb95=eb95,
  )
  watchlist = not triage_masked(tentative, min_n=min_n)
  return SignalMetrics(
    **{**tentative.__dict__, "watchlist": watchlist},
  )
