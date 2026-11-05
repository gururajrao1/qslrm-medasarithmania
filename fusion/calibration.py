"""Fusion calibration — fit weights vs BBW labels, freeze references, validate.

Pipeline order in Phase 3 is fusion -> calibration -> fusion-refit, so the
shipped scores already use fitted weights. Reference lives at
``data/processed/qslrm_reference.json`` (means/stds + weight set); the
refit pass and the API band helper read it, falling back to cohort stats.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import minimize
from sqlalchemy import select
from sqlalchemy.orm import Session

from fusion.scoring import fuse_risk, signal_strength, zscore
from qslrm_erd.models import GroundTruthLabel, OmicScore, RiskScore, SignalStat
from qslrm_erd.settings import get_settings

REFERENCE_FILENAME = "qslrm_reference.json"
DEFAULT_WEIGHTS = {"w_signal": 0.35, "w_omic": 0.30, "w_dose": 0.15, "w_serious": 0.20}
WEIGHT_KEYS = ("w_signal", "w_omic", "w_dose", "w_serious")


def reference_path() -> Path:
  settings = get_settings()
  return Path(settings.processed_data_dir) / REFERENCE_FILENAME


def load_reference() -> dict[str, Any] | None:
  try:
    return json.loads(reference_path().read_text(encoding="utf-8"))
  except (OSError, ValueError):
    return None


def save_reference(payload: dict[str, Any]) -> str:
  path = reference_path()
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
  return str(path)


def resolve_weights(model_version: str) -> dict[str, float]:
  """Fitted weights when a matching reference exists, else defaults."""
  ref = load_reference()
  weights = dict(DEFAULT_WEIGHTS)
  if ref and ref.get("model_version") == model_version:
    for key in WEIGHT_KEYS:
      try:
        weights[key] = float(ref["weights"][key])
      except (KeyError, TypeError, ValueError):
        continue
  return weights


def resolve_stats(
  model_version: str, cohort_stats: list[tuple[float, float]]
) -> tuple[list[tuple[float, float]], str]:
  """Frozen (mean, std) pairs when a matching reference exists, else cohort."""
  ref = load_reference()
  if ref and ref.get("model_version") == model_version and len(ref.get("stats", [])) == 4:
    try:
      frozen = [(float(m), float(s)) for m, s in ref["stats"]]
      return frozen, "frozen"
    except (TypeError, ValueError):
      pass
  return cohort_stats, "cohort"


def _feature_frame(session: Session, model_version: str) -> tuple[list[tuple[str, str]], dict]:
  """Mirror of run_fusion feature construction: raw values + cohort stats."""
  risk_rows = session.scalars(
    select(RiskScore).where(RiskScore.model_version == model_version)
  ).all()
  signals = {
    (s.drug_id, s.ae_term_id): s
    for s in session.scalars(
      select(SignalStat).where(SignalStat.model_version == model_version, SignalStat.period == "all")
    ).all()
  }
  omics = {
    (o.drug_id, o.ae_term_id): o
    for o in session.scalars(select(OmicScore).where(OmicScore.model_version == model_version)).all()
  }
  keys, sig_vals, omic_vals, dose_vals, serious_vals = [], [], [], [], []
  for rs in risk_rows:
    key = (rs.drug_id, rs.ae_term_id)
    keys.append(key)
    sig = signals.get(key)
    om = omics.get(key)
    sig_vals.append(
      signal_strength(
        sig.prr if sig else rs.prr,
        sig.ror if sig else rs.ror,
        sig.ebgm if sig else None,
        ror_ci_low=getattr(sig, "ror_ci_low", None) if sig else None,
        ic025=getattr(sig, "ic025", None) if sig else None,
        eb05=getattr(sig, "eb05", None) if sig else None,
      )
    )
    omic_vals.append(float(om.omic_risk) if om and om.omic_risk is not None else float(rs.omic_risk or 0.0))
    dose_vals.append(float(rs.dose_risk or 0.0))
    serious_vals.append(float(rs.serious_rate or 0.0))
  stats = [(float(np.mean(v)), float(np.std(v))) for v in (sig_vals, omic_vals, dose_vals, serious_vals)]
  frame = {
    "keys": keys,
    "z": [
      (zscore(sv, *stats[0]), zscore(ov, *stats[1]), zscore(dv, *stats[2]), zscore(sev, *stats[3]))
      for sv, ov, dv, sev in zip(sig_vals, omic_vals, dose_vals, serious_vals, strict=True)
    ],
    "stats": stats,
    "omics": omics,
  }
  return keys, frame


def _fit_logistic(X: np.ndarray, y: np.ndarray, l2: float = 1.0) -> np.ndarray | None:
  """L2 logistic regression (intercept + 4 weights) via L-BFGS; None if degenerate."""
  if len(set(y.tolist())) < 2 or len(y) < 8:
    return None

  def loss(theta: np.ndarray) -> float:
    z = X @ theta[1:] + theta[0]
    p = 1.0 / (1.0 + np.exp(-np.clip(z, -30.0, 30.0)))
    eps = 1e-9
    nll = -float(np.mean(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps)))
    return nll + l2 * float(np.sum(theta[1:] ** 2)) / len(y)

  x0 = np.zeros(X.shape[1] + 1)
  res = minimize(loss, x0, method="L-BFGS-B", options={"maxiter": 500})
  if not res.success:
    return None
  return np.asarray(res.x, dtype=float)


def roc_auc(y: list[int], s: list[float]) -> float | None:
  """Mann-Whitney AUC; None when single-class."""
  y = np.asarray(y, dtype=float)
  s = np.asarray(s, dtype=float)
  pos, neg = s[y == 1], s[y == 0]
  if len(pos) == 0 or len(neg) == 0:
    return None
  order = np.argsort(s)
  ranks = np.empty_like(order, dtype=float)
  ranks[order] = np.arange(1, len(s) + 1)
  auc = (float(np.sum(ranks[y == 1])) - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))
  return float(auc)


def precision_at_k(y: list[int], s: list[float], k: int = 10) -> float | None:
  if not y:
    return None
  k = max(1, min(k, len(y)))
  top = np.argsort(np.asarray(s, dtype=float))[::-1][:k]
  return float(np.mean([y[i] for i in top]))


def calibration_curve(y: list[int], s: list[float], bins: int = 5) -> list[dict[str, float]]:
  """Predicted fused/100 deciles vs observed BBW rate per bin."""
  y = np.asarray(y, dtype=float)
  s = np.asarray(s, dtype=float)
  edges = np.linspace(0.0, 1.0, bins + 1)
  curve = []
  for lo, hi in pairwise(edges):
    mask = (s / 100.0 >= lo) & (s / 100.0 < hi if hi < 1.0 else s / 100.0 <= hi)
    idx = np.nonzero(mask)[0]
    curve.append(
      {"bin_lo": float(lo), "bin_hi": float(hi), "n": len(idx),
       "observed_rate": float(np.mean(y[idx])) if len(idx) else 0.0}
    )
  return curve


def weight_tornado(
  frame: dict, weights: dict[str, float], *, delta: float = 0.10
) -> dict[str, Any]:
  """Rank stability under ±delta weight perturbation (mean |Δfused|, top-10 overlap)."""
  base_w = np.array([weights[k] for k in WEIGHT_KEYS], dtype=float)
  z = np.asarray(frame["z"], dtype=float)
  omics = frame["omics"]
  keys = frame["keys"]

  def fused_scores(w: np.ndarray) -> list[float]:
    out = []
    for (zs, zo, zd, zr), key in zip(z, keys, strict=True):
      om = omics.get(key)
      r = fuse_risk(
        float(zs), float(zo), float(zd), float(zr),
        w_signal=float(w[0]), w_omic=float(w[1]), w_dose=float(w[2]), w_serious=float(w[3]),
        s_off=float(om.s_off) if om else 0.0,
        s_trans=float(om.s_trans) if om else 0.0,
        s_gen=float(om.s_gen) if om else 0.0,
      )
      out.append(r.fused_score)
    return out

  base = fused_scores(base_w)
  base_top = set(np.argsort(np.asarray(base, dtype=float))[::-1][:10].tolist())
  per_weight = {}
  for i, key in enumerate(WEIGHT_KEYS):
    for sign in (1.0, -1.0):
      w = base_w.copy()
      w[i] = w[i] * (1.0 + sign * delta)
      alt = fused_scores(w)
      per_weight[f"{key}{'+' if sign > 0 else '-'}"] = {
        "mean_abs_change": float(np.mean(np.abs(np.asarray(alt) - np.asarray(base)))),
        "top10_overlap": len(base_top & set(np.argsort(np.asarray(alt))[::-1][:10].tolist())),
      }
  return {"delta": delta, "per_weight": per_weight}


def fused_band(
  z_vals: tuple[float, float, float, float],
  om_vals: tuple[float, float, float],
  weights: dict[str, float],
  *,
  delta: float = 0.10,
) -> dict[str, float]:
  """(lo, hi) fused band under ±delta per-weight perturbation for one pair."""
  scores = []
  base_w = [weights[k] for k in WEIGHT_KEYS]
  for i in range(4):
    for sign in (1.0, -1.0):
      w = list(base_w)
      w[i] = w[i] * (1.0 + sign * delta)
      r = fuse_risk(
        *z_vals,
        w_signal=w[0], w_omic=w[1], w_dose=w[2], w_serious=w[3],
        s_off=om_vals[0], s_trans=om_vals[1], s_gen=om_vals[2],
      )
      scores.append(r.fused_score)
  base = fuse_risk(
    *z_vals,
    w_signal=base_w[0], w_omic=base_w[1], w_dose=base_w[2], w_serious=base_w[3],
    s_off=om_vals[0], s_trans=om_vals[1], s_gen=om_vals[2],
  ).fused_score
  scores.append(base)
  return {"lo": float(min(scores)), "hi": float(max(scores)), "fused": float(base)}


def run_calibration(session: Session) -> dict[str, Any]:
  """Fit weights vs BBW labels, freeze reference, validate, tornado. Always saves."""
  settings = get_settings()
  model_version = settings.model_version
  keys, frame = _feature_frame(session, model_version)
  bbw = {(g.drug_id, g.ae_term_id) for g in session.scalars(select(GroundTruthLabel)).all()}
  y = [1 if k in bbw else 0 for k in keys]
  X = np.asarray(frame["z"], dtype=float)

  theta = _fit_logistic(X, np.asarray(y, dtype=float))
  fitted = theta is not None
  weights = dict(DEFAULT_WEIGHTS)
  intercept = 0.0
  if fitted:
    assert theta is not None
    intercept = float(theta[0])
    for key, val in zip(WEIGHT_KEYS, theta[1:], strict=True):
      weights[key] = float(val)

  fused_now = [r.fused_score for r in session.scalars(
    select(RiskScore).where(
      RiskScore.model_version == model_version, RiskScore.fused_score.is_not(None)
    )
  ).all()]
  n_pos = int(sum(y))
  summary: dict[str, Any] = {
    "fitted": fitted,
    "weights": weights,
    "intercept": intercept,
    "n_pairs": len(keys),
    "n_bbw": n_pos,
    "roc_auc": None,
    "precision_at_k": None,
    "calibration": [],
    "tornado": weight_tornado(frame, weights),
    "temporal_note": "Temporal train-past/test-next validation needs periodized ground truth; labels are period-free, so validation is cross-sectional.",
  }
  if fused_now and len(fused_now) == len(y):
    summary["roc_auc"] = roc_auc(y, [float(v or 0.0) for v in fused_now])
    summary["precision_at_k"] = precision_at_k(y, [float(v or 0.0) for v in fused_now])
    summary["calibration"] = calibration_curve(y, [float(v or 0.0) for v in fused_now])

  ref_path = save_reference(
    {
      "model_version": model_version,
      "weights": weights,
      "intercept": intercept,
      "fitted": fitted,
      "stats": frame["stats"],
      "n_pairs": len(keys),
      "n_bbw": n_pos,
      "saved_at": datetime.now(UTC).isoformat(),
    }
  )
  summary["reference_path"] = ref_path
  return summary
