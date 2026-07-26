"""Run PV signal detection and persist signal_stat (+ seed risk_score PV fields)."""

from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from qslrm_erd.models import RiskScore, SignalStat
from qslrm_erd.settings import get_settings
from signals.contingency_builder import build_contingency_map, dose_risk_map, serious_rate_map
from signals.disproportionality import compute_signals


def _finite(x: float | None) -> float | None:
  if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
    return None
  return float(x)


def run_signal_detection(session: Session, *, period: str = "all") -> dict:
  settings = get_settings()
  model_version = settings.model_version
  contingencies = build_contingency_map(session)
  serious = serious_rate_map(session)
  doses = dose_risk_map(session)

  inserted = updated = 0
  for (drug_id, ae_term_id), contingency in contingencies.items():
    metrics = compute_signals(contingency, min_n=3)
    if metrics is None:
      continue
    sr = serious.get((drug_id, ae_term_id))
    existing = session.scalar(
      select(SignalStat).where(
        SignalStat.drug_id == drug_id,
        SignalStat.ae_term_id == ae_term_id,
        SignalStat.period == period,
        SignalStat.model_version == model_version,
      )
    )
    payload = dict(
      drug_id=drug_id,
      ae_term_id=ae_term_id,
      period=period,
      n11=metrics.n11,
      n1_=metrics.n1_,
      n_1=metrics.n_1,
      n__=metrics.n__,
      prr=_finite(metrics.prr),
      ror=_finite(metrics.ror),
      ror_ci_low=_finite(metrics.ror_ci_low),
      ror_ci_high=_finite(metrics.ror_ci_high),
      ic=_finite(metrics.ic),
      ebgm=_finite(metrics.ebgm),
      serious_rate=sr,
      model_version=model_version,
    )
    if existing is None:
      session.add(SignalStat(**payload))
      inserted += 1
    else:
      for k, v in payload.items():
        setattr(existing, k, v)
      updated += 1

    # Seed / refresh risk_score PV columns (fusion left for Phase 3)
    rs = session.scalar(
      select(RiskScore).where(
        RiskScore.drug_id == drug_id,
        RiskScore.ae_term_id == ae_term_id,
        RiskScore.model_version == model_version,
      )
    )
    dose_risk = doses.get((drug_id, ae_term_id), 0.0)
    if rs is None:
      session.add(
        RiskScore(
          drug_id=drug_id,
          ae_term_id=ae_term_id,
          n_reports=metrics.n11,
          prr=_finite(metrics.prr),
          ror=_finite(metrics.ror),
          dose_risk=dose_risk,
          serious_rate=sr,
          action_needed=False,
          rising_signal=False,
          model_version=model_version,
        )
      )
    else:
      rs.n_reports = metrics.n11
      rs.prr = _finite(metrics.prr)
      rs.ror = _finite(metrics.ror)
      rs.dose_risk = dose_risk
      rs.serious_rate = sr

  session.commit()
  return {
    "pairs": len(contingencies),
    "signal_stat_inserted": inserted,
    "signal_stat_updated": updated,
  }


def seed_period_signals_for_velocity(session: Session) -> dict:
  """Synthesize prior/current quarterly SignalStat rows so ΔROR can be computed.

  Uses overall 'all' period ROR: 2023q4 ≈ 0.6×, 2024q1 ≈ 1.3× for rising demos.
  """
  settings = get_settings()
  model_version = settings.model_version
  rows = session.scalars(
    select(SignalStat).where(SignalStat.model_version == model_version, SignalStat.period == "all")
  ).all()
  inserted = 0
  for i, s in enumerate(rows):
    if s.ror is None:
      continue
    # make half the pairs rising (double-ish), half stable
    rising = i % 2 == 0
    for period, factor in (("2023q4", 0.55 if rising else 0.95), ("2024q1", 1.35 if rising else 1.0)):
      existing = session.scalar(
        select(SignalStat).where(
          SignalStat.drug_id == s.drug_id,
          SignalStat.ae_term_id == s.ae_term_id,
          SignalStat.period == period,
          SignalStat.model_version == model_version,
        )
      )
      ror = max(0.1, float(s.ror) * factor)
      payload = dict(
        drug_id=s.drug_id,
        ae_term_id=s.ae_term_id,
        period=period,
        n11=s.n11,
        n1_=s.n1_,
        n_1=s.n_1,
        n__=s.n__,
        prr=_finite((s.prr or ror) * factor),
        ror=_finite(ror),
        ror_ci_low=s.ror_ci_low,
        ror_ci_high=s.ror_ci_high,
        ic=s.ic,
        ebgm=s.ebgm,
        serious_rate=s.serious_rate,
        model_version=model_version,
      )
      if existing is None:
        session.add(SignalStat(**payload))
        inserted += 1
      else:
        for k, v in payload.items():
          setattr(existing, k, v)
  session.commit()
  return {"period_signal_rows": inserted}
