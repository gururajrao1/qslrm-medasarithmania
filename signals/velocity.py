"""Signal velocity engine — ΔROR across FAERS periods."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from qslrm_erd.models import RiskScore, SignalStat, SignalVelocity
from qslrm_erd.settings import get_settings


def compute_signal_velocity(session: Session) -> dict:
  settings = get_settings()
  model_version = settings.model_version
  rows = session.scalars(
    select(SignalStat).where(
      SignalStat.model_version == model_version,
      SignalStat.period != "all",
      SignalStat.ror.is_not(None),
    )
  ).all()

  by_pair: dict[tuple[str, str], list[SignalStat]] = {}
  for r in rows:
    by_pair.setdefault((r.drug_id, r.ae_term_id), []).append(r)

  inserted = updated = rising_n = 0
  for (drug_id, ae_term_id), stats in by_pair.items():
    ordered = sorted(stats, key=lambda s: s.period)
    if len(ordered) < 2:
      continue
    a, b = ordered[-2], ordered[-1]
    if a.ror is None or b.ror is None or a.ror <= 0:
      continue
    delta = float(b.ror - a.ror)
    # assume adjacent quarterly periods → Δt = 1 quarter
    velocity = delta / 1.0
    n_periods = len(ordered)
    ratio = (b.ror / a.ror) if a.ror else 0.0
    strong_step = ratio >= 2.0 and delta > 0 and velocity >= settings.rising_velocity_threshold
    if n_periods >= 3:
      c = ordered[-3]
      monotonic = (
        c.ror is not None and a.ror is not None and b.ror is not None
        and c.ror <= a.ror <= b.ror and b.ror > c.ror
      )
      ci_gap = (
        a.ror_ci_low is not None and b.ror_ci_low is not None
        and b.ror_ci_low > (a.ror_ci_high if a.ror_ci_high is not None else a.ror)
      )
      rising = bool(strong_step and (monotonic or ci_gap))
    else:
      rising = bool(strong_step)
    existing = session.scalar(
      select(SignalVelocity).where(
        SignalVelocity.drug_id == drug_id,
        SignalVelocity.ae_term_id == ae_term_id,
        SignalVelocity.period_from == a.period,
        SignalVelocity.period_to == b.period,
        SignalVelocity.model_version == model_version,
      )
    )
    payload = {
      "drug_id": drug_id,
      "ae_term_id": ae_term_id,
      "period_from": a.period,
      "period_to": b.period,
      "ror_from": float(a.ror),
      "ror_to": float(b.ror),
      "delta_ror": delta,
      "velocity": velocity,
      "rising": rising,
      "model_version": model_version,
    }
    if existing is None:
      session.add(SignalVelocity(**payload))
      inserted += 1
    else:
      for k, v in payload.items():
        setattr(existing, k, v)
      updated += 1
    if rising:
      rising_n += 1

  # Baseline ΔROR for fused pairs missing velocity so UI sort never blanks
  fallback = ensure_velocity_fallback(session)
  session.commit()
  return {
    "velocity_inserted": inserted,
    "velocity_updated": updated,
    "rising": rising_n,
    "velocity_fallback": fallback,
  }


def ensure_velocity_fallback(session: Session) -> dict:
  """Neutral baseline row for pairs with no period history (ΔROR = 0, never rising)."""
  settings = get_settings()
  model_version = settings.model_version
  pairs = session.scalars(
    select(RiskScore).where(RiskScore.model_version == model_version)
  ).all()
  inserted = 0
  for rs in pairs:
    existing = session.scalar(
      select(SignalVelocity).where(
        SignalVelocity.drug_id == rs.drug_id,
        SignalVelocity.ae_term_id == rs.ae_term_id,
        SignalVelocity.model_version == model_version,
      )
    )
    if existing is not None:
      continue
    ror = float(rs.ror or 1.0)
    # No seriousness bump: baseline rows stay neutral (ΔROR = 0, never rising).
    delta = 0.0
    session.add(
      SignalVelocity(
        drug_id=rs.drug_id,
        ae_term_id=rs.ae_term_id,
        period_from="baseline",
        period_to="current",
        ror_from=max(0.1, ror),
        ror_to=max(0.1, ror),
        delta_ror=delta,
        velocity=delta,
        rising=False,
        model_version=model_version,
      )
    )
    inserted += 1
  return {"fallback_inserted": inserted}
