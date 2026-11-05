"""Unit tests for PRR / ROR / IC / EBGM — no database required."""

from __future__ import annotations

import math

from signals import Contingency, compute_signals


def test_known_signal_elevated_ror():
  # Classic elevated cell: drug-event much more common than background
  c = Contingency(n11=50, n10=50, n01=50, n00=850)
  m = compute_signals(c)
  assert m is not None
  assert m.prr > 1.0
  assert m.ror > 1.0
  assert m.ror_ci_low > 1.0
  assert m.n11 == 50


def test_null_ish_ror_near_one():
  c = Contingency(n11=10, n10=90, n01=100, n00=800)
  m = compute_signals(c)
  assert m is not None
  assert 0.5 < m.ror < 2.0


def test_rare_event_still_returns_ebgm():
  c = Contingency(n11=2, n10=8, n01=20, n00=970)
  m = compute_signals(c, min_n=3)
  assert m is not None
  assert not math.isnan(m.ebgm)


def test_zero_support_returns_none():
  c = Contingency(n11=0, n10=10, n01=5, n00=100)
  assert compute_signals(c) is None
def test_ebgm_credible_interval_ordered():
  from signals import ebgm_mgps

  ebgm, eb05, eb95 = ebgm_mgps(Contingency(n11=50, n10=50, n01=50, n00=850))
  assert eb05 <= ebgm <= eb95
  assert math.isfinite(ebgm)


def test_prr_chi_square_nonnegative_and_strong():
  from signals import prr_chi_square

  strong = prr_chi_square(Contingency(n11=50, n10=50, n01=50, n00=850))
  assert strong >= 4.0
  weak = prr_chi_square(Contingency(n11=10, n10=90, n01=100, n00=800))
  assert weak >= 0.0


def test_ic025_below_ic():
  from signals.disproportionality import ic_credible_low, information_component

  c = Contingency(n11=50, n10=50, n01=50, n00=850)
  assert ic_credible_low(c) <= information_component(c)


def test_triage_masking_rules():
  from signals import triage_decision, triage_masked

  strong = compute_signals(Contingency(n11=50, n10=50, n01=50, n00=850))
  assert strong is not None
  assert triage_masked(strong) is True
  assert strong.watchlist is False
  tiny = compute_signals(Contingency(n11=1, n10=90, n01=100, n00=800), min_n=3)
  assert tiny is not None
  assert triage_masked(tiny) is False
  assert tiny.watchlist is True
  masked, watchlist, metrics = triage_decision(0, 10, 5, 100)
  assert (masked, watchlist, metrics) == (False, True, None)
