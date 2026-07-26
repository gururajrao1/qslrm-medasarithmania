"""Phase 3 fusion runner — 4-tier attrs + seriousness + action flags."""

from __future__ import annotations

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from fusion.decisions import action_flag_from_cards, build_decisions
from fusion.scoring import fuse_risk, signal_strength, zscore
from qslrm_erd.models import AeTerm, Drug, GroundTruthLabel, OmicScore, RiskScore, SignalStat, SignalVelocity
from qslrm_erd.settings import get_settings


def run_fusion(session: Session) -> dict:
  settings = get_settings()
  model_version = settings.model_version

  risk_rows = session.scalars(
    select(RiskScore).where(RiskScore.model_version == model_version)
  ).all()
  if not risk_rows:
    return {"fused": 0, "note": "no risk_score rows — run Phase 2 first"}

  signals = {
    (s.drug_id, s.ae_term_id): s
    for s in session.scalars(
      select(SignalStat).where(SignalStat.model_version == model_version, SignalStat.period == "all")
    ).all()
  }
  omics = {
    (o.drug_id, o.ae_term_id): o
    for o in session.scalars(
      select(OmicScore).where(OmicScore.model_version == model_version)
    ).all()
  }
  rising = {
    (v.drug_id, v.ae_term_id)
    for v in session.scalars(
      select(SignalVelocity).where(
        SignalVelocity.model_version == model_version, SignalVelocity.rising.is_(True)
      )
    ).all()
  }
  bbw = {
    (g.drug_id, g.ae_term_id)
    for g in session.scalars(select(GroundTruthLabel)).all()
  }

  sig_vals: list[float] = []
  omic_vals: list[float] = []
  dose_vals: list[float] = []
  serious_vals: list[float] = []
  keys: list[tuple[str, str]] = []

  for rs in risk_rows:
    key = (rs.drug_id, rs.ae_term_id)
    keys.append(key)
    sig = signals.get(key)
    om = omics.get(key)
    strength = signal_strength(
      sig.prr if sig else rs.prr,
      sig.ror if sig else rs.ror,
      sig.ebgm if sig else None,
    )
    omic = float(om.omic_risk) if om and om.omic_risk is not None else float(rs.omic_risk or 0.0)
    dose = float(rs.dose_risk or 0.0)
    serious = float(rs.serious_rate or 0.0)
    sig_vals.append(strength)
    omic_vals.append(omic)
    dose_vals.append(dose)
    serious_vals.append(serious)

  stats = [
    (float(np.mean(v)), float(np.std(v)))
    for v in (sig_vals, omic_vals, dose_vals, serious_vals)
  ]

  fused_n = 0
  for rs, key, sv, ov, dv, sev in zip(
    risk_rows, keys, sig_vals, omic_vals, dose_vals, serious_vals, strict=True
  ):
    om = omics.get(key)
    result = fuse_risk(
      zscore(sv, *stats[0]),
      zscore(ov, *stats[1]),
      zscore(dv, *stats[2]),
      zscore(sev, *stats[3]),
      s_off=float(om.s_off) if om else 0.0,
      s_trans=float(om.s_trans) if om else 0.0,
      s_gen=float(om.s_gen) if om else 0.0,
    )
    rs.fused_score = result.fused_score
    rs.attr_dose = result.attr_dose
    rs.attr_offtarget = result.attr_offtarget
    rs.attr_transcriptomic = result.attr_transcriptomic
    rs.attr_genetic = result.attr_genetic
    if om is not None:
      rs.omic_risk = om.omic_risk
    is_rising = key in rising
    rs.rising_signal = is_rising
    drug = session.get(Drug, rs.drug_id)
    ae = session.get(AeTerm, rs.ae_term_id)
    cards = build_decisions(
      drug_name=drug.preferred_name if drug else rs.drug_id,
      pt_string=ae.pt_string if ae else rs.ae_term_id,
      fused_score=rs.fused_score,
      attr_dose=rs.attr_dose,
      attr_offtarget=rs.attr_offtarget,
      attr_transcriptomic=rs.attr_transcriptomic,
      attr_genetic=rs.attr_genetic,
      rising_signal=is_rising,
      is_bbw=key in bbw,
    )
    needed, flag = action_flag_from_cards(cards, rs.fused_score, is_rising)
    rs.action_needed = needed
    rs.action_flag = flag
    fused_n += 1

  session.commit()
  scores = [r.fused_score for r in risk_rows if r.fused_score is not None]
  return {
    "fused": fused_n,
    "fused_score_min": min(scores) if scores else None,
    "fused_score_max": max(scores) if scores else None,
    "fused_score_mean": float(np.mean(scores)) if scores else None,
    "action_needed": sum(1 for r in risk_rows if r.action_needed),
  }
