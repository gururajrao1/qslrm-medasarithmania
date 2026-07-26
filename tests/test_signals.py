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
