"""Fusion + attribution unit tests."""

from __future__ import annotations

from fusion import fuse_risk, split_omic_attribution


def _attr_sum(r) -> float:
  return r.attr_dose + r.attr_offtarget + r.attr_transcriptomic + r.attr_genetic


def test_fuse_score_bounds():
  r = fuse_risk(signal_z=2.0, omic_z=1.0, dose_z=0.5, serious_z=0.3)
  assert 0.0 <= r.fused_score <= 100.0
  assert abs(_attr_sum(r) - 1.0) < 1e-6


def test_higher_signal_raises_score():
  low = fuse_risk(signal_z=-1.0, omic_z=0.0, dose_z=0.0)
  high = fuse_risk(signal_z=2.0, omic_z=0.0, dose_z=0.0)
  assert high.fused_score > low.fused_score


def test_split_omic_attribution():
  off, gen = split_omic_attribution(0.6, s_off=2.0, s_gen=1.0)
  assert abs(off + gen - 0.6) < 1e-9
  assert off > gen


def test_transcriptomic_split_when_s_trans_high():
  r = fuse_risk(
    signal_z=1.0, omic_z=1.0, dose_z=0.1, serious_z=0.0, s_off=0.2, s_trans=3.0, s_gen=0.2
  )
  assert r.attr_transcriptomic > r.attr_offtarget
  assert abs(_attr_sum(r) - 1.0) < 1e-6
