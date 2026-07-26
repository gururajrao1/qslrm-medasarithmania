"""Risk fusion + 4-tier attribution + seriousness term."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def sigmoid(x: float) -> float:
  return float(1.0 / (1.0 + np.exp(-x)))


def zscore(value: float, mean: float, std: float) -> float:
  if std <= 0:
    return 0.0
  return (value - mean) / std


@dataclass(frozen=True)
class FusionResult:
  fused_score: float
  attr_dose: float
  attr_offtarget: float
  attr_transcriptomic: float
  attr_genetic: float
  z_signal: float
  z_omic: float
  z_dose: float
  z_serious: float


def fuse_risk(
  signal_z: float,
  omic_z: float,
  dose_z: float,
  serious_z: float = 0.0,
  *,
  w_signal: float = 0.35,
  w_omic: float = 0.30,
  w_dose: float = 0.15,
  w_serious: float = 0.20,
  s_off: float = 0.0,
  s_trans: float = 0.0,
  s_gen: float = 0.0,
) -> FusionResult:
  """Fused = 100 · σ(w1 z_sig + w2 z_omic + w3 z_dose + w4 z_serious)."""
  linear = w_signal * signal_z + w_omic * omic_z + w_dose * dose_z + w_serious * serious_z
  fused = 100.0 * sigmoid(linear)

  dose_mass = abs(w_dose * dose_z)
  omic_mass = abs(w_omic * omic_z)
  signal_mass = abs(w_signal * signal_z)
  serious_mass = abs(w_serious * serious_z)

  off_o, tr_o, gen_o = split_three(omic_mass, s_off, s_trans, s_gen)
  off_s, tr_s, gen_s = split_three(signal_mass + serious_mass * 0.5, s_off, s_trans, s_gen)
  # remaining seriousness leans dose/exposure
  dose_mass += serious_mass * 0.5

  raw = np.array([dose_mass, off_o + off_s, tr_o + tr_s, gen_o + gen_s], dtype=float)
  total = float(raw.sum())
  if total <= 0:
    attrs = (0.25, 0.25, 0.25, 0.25)
  else:
    attrs = tuple(float(x / total) for x in raw)

  return FusionResult(
    fused_score=fused,
    attr_dose=attrs[0],
    attr_offtarget=attrs[1],
    attr_transcriptomic=attrs[2],
    attr_genetic=attrs[3],
    z_signal=signal_z,
    z_omic=omic_z,
    z_dose=dose_z,
    z_serious=serious_z,
  )


def split_three(mass: float, a: float, b: float, c: float) -> tuple[float, float, float]:
  denom = abs(a) + abs(b) + abs(c)
  if denom <= 0 or mass <= 0:
    return mass / 3, mass / 3, mass / 3
  return mass * abs(a) / denom, mass * abs(b) / denom, mass * abs(c) / denom


def split_omic_attribution(attr_omic_mass: float, s_off: float, s_gen: float) -> tuple[float, float]:
  """Back-compat 2-way split."""
  denom = abs(s_off) + abs(s_gen)
  if denom <= 0 or attr_omic_mass <= 0:
    return attr_omic_mass * 0.5, attr_omic_mass * 0.5
  return attr_omic_mass * abs(s_off) / denom, attr_omic_mass * abs(s_gen) / denom


def signal_strength(prr: float | None, ror: float | None, ebgm: float | None) -> float:
  for v in (ebgm, ror, prr):
    if v is not None and np.isfinite(v) and v > 0:
      return float(np.log(v))
  return 0.0
