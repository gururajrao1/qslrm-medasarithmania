"""Demographic stratification of FAERS signals.

Stratum rows carry crude lift (masked when n < 3); each pair also gets one
``mh_pooled/sex`` row with the Mantel-Haenszel ROR across sex strata, so the
UI can show an age/sex-adjusted effect instead of a crude share ratio.
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from qslrm_erd.models import DemographicSignal, PvCase, PvDrugEvent
from qslrm_erd.settings import get_settings


def _mh_ror(
  pair: tuple[str, str],
  drug_sex: dict[tuple[str, str], set[str]],
  ae_sex: dict[tuple[str, str], set[str]],
  all_sex: dict[str, set[str]],
  pair_sex: dict[tuple[str, str, str], set[str]],
) -> float | None:
  """Mantel-Haenszel ROR across sex strata; None when unsupported."""
  drug_id, ae_id = pair
  num = den = 0.0
  valid = 0
  for sex, cases in all_sex.items():
    if not sex or not cases:
      continue
    d_cases = drug_sex.get((drug_id, sex), set())
    e_cases = ae_sex.get((ae_id, sex), set())
    a = len(pair_sex.get((drug_id, ae_id, sex), set()))
    b = len(d_cases - e_cases)
    c = len(e_cases - d_cases)
    d = len(set(cases) - d_cases - e_cases)
    if min(a, b, c, d) < 1:
      continue
    n = len(cases)
    num += a * d / n
    den += b * c / n
    valid += 1
  if valid < 1 or den <= 0:
    return None
  return num / den


def compute_demographic_signals(session: Session) -> dict:
  settings = get_settings()
  model_version = settings.model_version
  rows = session.execute(
    select(
      PvDrugEvent.drug_id,
      PvDrugEvent.ae_term_id,
      PvDrugEvent.case_id,
      PvCase.sex,
      PvCase.age_group,
      PvCase.country,
    ).join(PvCase, PvCase.case_id == PvDrugEvent.case_id)
  ).all()

  pair_tot: dict[tuple[str, str], int] = defaultdict(int)
  strata: dict[tuple[str, str, str, str], int] = defaultdict(int)
  global_stratum: dict[tuple[str, str], int] = defaultdict(int)
  drug_sex: dict[tuple[str, str], set[str]] = defaultdict(set)
  ae_sex: dict[tuple[str, str], set[str]] = defaultdict(set)
  all_sex: dict[str, set[str]] = defaultdict(set)
  pair_sex: dict[tuple[str, str, str], set[str]] = defaultdict(set)

  for drug_id, ae_id, case_id, sex, age_group, country in rows:
    pair = (drug_id, ae_id)
    pair_tot[pair] += 1
    for stype, sval in (("sex", sex), ("age_group", age_group), ("country", country)):
      if not sval:
        continue
      strata[(drug_id, ae_id, stype, sval)] += 1
      global_stratum[(stype, sval)] += 1
    if sex:
      drug_sex[(drug_id, sex)].add(case_id)
      ae_sex[(ae_id, sex)].add(case_id)
      all_sex[sex].add(case_id)
      pair_sex[(drug_id, ae_id, sex)].add(case_id)

  total_events = max(sum(pair_tot.values()), 1)
  inserted = updated = 0

  def _upsert(payload: dict) -> None:
    nonlocal inserted, updated
    existing = session.scalar(
      select(DemographicSignal).where(
        DemographicSignal.drug_id == payload["drug_id"],
        DemographicSignal.ae_term_id == payload["ae_term_id"],
        DemographicSignal.stratum_type == payload["stratum_type"],
        DemographicSignal.stratum_value == payload["stratum_value"],
        DemographicSignal.model_version == model_version,
      )
    )
    if existing is None:
      session.add(DemographicSignal(**payload))
      inserted += 1
    else:
      for k, v in payload.items():
        setattr(existing, k, v)
      updated += 1

  for (drug_id, ae_id, stype, sval), n in strata.items():
    share = n / pair_tot[(drug_id, ae_id)]
    bg = global_stratum[(stype, sval)] / total_events
    # Mask noisy small cells instead of showing a spurious lift.
    lift = (share / bg) if (bg > 0 and n >= 3) else None
    _upsert(
      {
        "drug_id": drug_id,
        "ae_term_id": ae_id,
        "stratum_type": stype,
        "stratum_value": sval,
        "n_reports": n,
        "share": share,
        "lift_vs_background": lift,
        "mh_ror": None,
        "model_version": model_version,
      }
    )

  mh_n = 0
  for pair, tot in pair_tot.items():
    mh = _mh_ror(pair, drug_sex, ae_sex, all_sex, pair_sex)
    _upsert(
      {
        "drug_id": pair[0],
        "ae_term_id": pair[1],
        "stratum_type": "mh_pooled",
        "stratum_value": "sex",
        "n_reports": tot,
        "share": 1.0,
        "lift_vs_background": None,
        "mh_ror": mh,
        "model_version": model_version,
      }
    )
    if mh is not None:
      mh_n += 1
  session.commit()
  return {"demo_inserted": inserted, "demo_updated": updated, "demo_mh_pooled": mh_n}
