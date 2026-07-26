"""Demographic stratification of FAERS signals."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from qslrm_erd.models import DemographicSignal, PvCase, PvDrugEvent
from qslrm_erd.settings import get_settings


def compute_demographic_signals(session: Session) -> dict:
  settings = get_settings()
  model_version = settings.model_version
  rows = session.execute(
    select(
      PvDrugEvent.drug_id,
      PvDrugEvent.ae_term_id,
      PvCase.sex,
      PvCase.age_group,
      PvCase.country,
    ).join(PvCase, PvCase.case_id == PvDrugEvent.case_id)
  ).all()

  pair_tot: dict[tuple[str, str], int] = defaultdict(int)
  strata: dict[tuple[str, str, str, str], int] = defaultdict(int)
  global_stratum: dict[tuple[str, str], int] = defaultdict(int)

  for drug_id, ae_id, sex, age_group, country in rows:
    pair = (drug_id, ae_id)
    pair_tot[pair] += 1
    for stype, sval in (("sex", sex), ("age_group", age_group), ("country", country)):
      if not sval:
        continue
      strata[(drug_id, ae_id, stype, sval)] += 1
      global_stratum[(stype, sval)] += 1

  total_events = max(sum(pair_tot.values()), 1)
  inserted = updated = 0
  for (drug_id, ae_id, stype, sval), n in strata.items():
    share = n / pair_tot[(drug_id, ae_id)]
    bg = global_stratum[(stype, sval)] / total_events
    lift = (share / bg) if bg > 0 else None
    existing = session.scalar(
      select(DemographicSignal).where(
        DemographicSignal.drug_id == drug_id,
        DemographicSignal.ae_term_id == ae_id,
        DemographicSignal.stratum_type == stype,
        DemographicSignal.stratum_value == sval,
        DemographicSignal.model_version == model_version,
      )
    )
    payload = dict(
      drug_id=drug_id,
      ae_term_id=ae_id,
      stratum_type=stype,
      stratum_value=sval,
      n_reports=n,
      share=share,
      lift_vs_background=lift,
      model_version=model_version,
    )
    if existing is None:
      session.add(DemographicSignal(**payload))
      inserted += 1
    else:
      for k, v in payload.items():
        setattr(existing, k, v)
      updated += 1
  session.commit()
  return {"demo_inserted": inserted, "demo_updated": updated}
