"""Build 2×2 contingency tables from pv_drug_event."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from qslrm_erd.models import AeTerm, PvCase, PvDrugEvent
from signals.disproportionality import Contingency


def build_contingency_map(session: Session) -> dict[tuple[str, str], Contingency]:
  """Return (drug_id, ae_term_id) → Contingency for all observed pairs.

  Counting grain = distinct case_id links in pv_drug_event (one row per case–drug–PT).
  """
  rows = session.execute(
    select(
      PvDrugEvent.drug_id,
      PvDrugEvent.ae_term_id,
      PvDrugEvent.case_id,
      PvCase.serious,
    ).join(PvCase, PvCase.case_id == PvDrugEvent.case_id)
  ).all()

  # pair counts and serious counts
  pair_n: dict[tuple[str, str], int] = defaultdict(int)
  pair_serious: dict[tuple[str, str], int] = defaultdict(int)
  drug_n: dict[str, int] = defaultdict(int)
  ae_n: dict[str, int] = defaultdict(int)
  # Use distinct (drug, case) and (ae, case) carefully — for FAERS MVP each link is unique

  drug_case: set[tuple[str, str]] = set()
  ae_case: set[tuple[str, str]] = set()
  all_cases: set[str] = set()

  for drug_id, ae_term_id, case_id, serious in rows:
    pair = (drug_id, ae_term_id)
    pair_n[pair] += 1
    if serious:
      pair_serious[pair] += 1
    drug_case.add((drug_id, case_id))
    ae_case.add((ae_term_id, case_id))
    all_cases.add(case_id)

  for drug_id, _case in drug_case:
    drug_n[drug_id] += 1
  for ae_term_id, _case in ae_case:
    ae_n[ae_term_id] += 1

  # Total reporting units = number of drug–event link rows (standard FAERS 2×2 on reports)
  # Here n__ = total link rows
  n_total = len(rows)
  if n_total == 0:
    return {}

  # Recompute using link-row margins (more standard for PRR on event rows)
  drug_link: dict[str, int] = defaultdict(int)
  ae_link: dict[str, int] = defaultdict(int)
  for drug_id, ae_term_id, _case_id, _serious in rows:
    drug_link[drug_id] += 1
    ae_link[ae_term_id] += 1

  out: dict[tuple[str, str], Contingency] = {}
  for (drug_id, ae_term_id), n11 in pair_n.items():
    n1_ = drug_link[drug_id]
    n_1 = ae_link[ae_term_id]
    n10 = n1_ - n11
    n01 = n_1 - n11
    n00 = n_total - n11 - n10 - n01
    out[(drug_id, ae_term_id)] = Contingency(
      n11=n11,
      n10=max(n10, 0),
      n01=max(n01, 0),
      n00=max(n00, 0),
    )
  return out


def serious_rate_map(session: Session) -> dict[tuple[str, str], float]:
  rows = session.execute(
    select(PvDrugEvent.drug_id, PvDrugEvent.ae_term_id, PvCase.serious).join(
      PvCase, PvCase.case_id == PvDrugEvent.case_id
    )
  ).all()
  tot: dict[tuple[str, str], int] = defaultdict(int)
  ser: dict[tuple[str, str], int] = defaultdict(int)
  for drug_id, ae_term_id, serious in rows:
    key = (drug_id, ae_term_id)
    tot[key] += 1
    if serious:
      ser[key] += 1
  return {k: (ser[k] / tot[k] if tot[k] else 0.0) for k in tot}


def dose_risk_map(session: Session) -> dict[tuple[str, str], float]:
  """Proxy: share of links with dose_text present (0–1)."""
  rows = session.execute(
    select(PvDrugEvent.drug_id, PvDrugEvent.ae_term_id, PvDrugEvent.dose_text)
  ).all()
  tot: dict[tuple[str, str], int] = defaultdict(int)
  with_dose: dict[tuple[str, str], int] = defaultdict(int)
  for drug_id, ae_term_id, dose_text in rows:
    key = (drug_id, ae_term_id)
    tot[key] += 1
    if dose_text:
      with_dose[key] += 1
  return {k: (with_dose[k] / tot[k] if tot[k] else 0.0) for k in tot}


def ae_pt_lookup(session: Session) -> dict[str, str]:
  return {a.ae_term_id: a.pt_string for a in session.scalars(select(AeTerm)).all()}
