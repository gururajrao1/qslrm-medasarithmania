"""Python reference implementation of OmicEngine (mirrors Julia math)."""

from __future__ import annotations

import math
from dataclasses import dataclass

TOX_WEIGHTS = {
  "hepatotox": 1.0,
  "dermal": 0.7,
  "vascular": 0.8,
  "cardio": 0.9,
}


def soff(affinities_nm: list[float], is_off: list[bool], *, eps: float = 1e-9) -> float:
  assert len(affinities_nm) == len(is_off)
  s = 0.0
  for aff, off in zip(affinities_nm, is_off, strict=True):
    if off:
      s += 1.0 / (math.log10(float(aff) + 1.0) + eps)
  return s


def spath(pathway_hits: list[bool], tox_weights: list[float]) -> float:
  assert len(pathway_hits) == len(tox_weights)
  return float(sum(w for hit, w in zip(pathway_hits, tox_weights, strict=True) if hit))


def strans(z_scores: list[float], tox_weights: list[float]) -> float:
  """S_trans = Σ |z_g| · w_tox (LINCS L1000 perturbation load)."""
  assert len(z_scores) == len(tox_weights)
  return float(sum(abs(z) * w for z, w in zip(z_scores, tox_weights, strict=True)))


def sgen(effect_sizes: list[float], related_mask: list[bool]) -> float:
  assert len(effect_sizes) == len(related_mask)
  return float(sum(abs(e) for e, m in zip(effect_sizes, related_mask, strict=True) if m))


def somic(
  s_off: float,
  s_trans: float,
  s_gen: float,
  *,
  alpha: float = 1.0,
  beta: float = 1.0,
  gamma: float = 1.0,
) -> float:
  x = alpha * s_off + beta * s_trans + gamma * s_gen
  return float(1.0 / (1.0 + math.exp(-x)))


@dataclass(frozen=True)
class OmicComponents:
  s_off: float
  s_path: float
  s_trans: float
  s_gen: float
  omic_risk: float
  engine: str = "python"


def tox_weight_for_tag(tag: str | None) -> float:
  if not tag:
    return 0.3
  return TOX_WEIGHTS.get(tag.lower(), 0.3)


def components_with_engine(
  s_off: float,
  s_path: float,
  s_trans: float,
  s_gen: float,
  *,
  prefer_julia: bool = False,
) -> OmicComponents:
  _ = prefer_julia  # Julia bridge optional; Python is source of truth for CI
  risk = somic(s_off, s_trans, s_gen)
  return OmicComponents(
    s_off=s_off,
    s_path=s_path,
    s_trans=s_trans,
    s_gen=s_gen,
    omic_risk=risk,
    engine="python",
  )
