"""EudraVigilance / OpenVigil-style EU PV fixture ingest."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ingest.literature import _ensure_ae
from qslrm_erd.models import AeTerm, PvCase, PvDrugEvent


def ingest_eudravigilance(session: Session, payload: dict[str, Any]) -> dict:
  """payload: {drug_id: [{case_id, ae, serious, country, report_date}]}"""
  cases_ins = events_ins = 0
  for drug_id, rows in (payload or {}).items():
    for row in rows or []:
      ae_id = _ensure_ae(session, row["ae"])
      ae = session.get(AeTerm, ae_id)
      if ae and row.get("meddra_pt_code") and not ae.meddra_pt_code:
        ae.meddra_pt_code = str(row["meddra_pt_code"])

      case_id = row["case_id"]
      existing_case = session.get(PvCase, case_id)
      if existing_case is None:
        session.add(
          PvCase(
            case_id=case_id,
            source_period="eudravigilance",
            source_region="EU",
            report_date=_parse_date(row.get("report_date")),
            sex=row.get("sex"),
            age_group=row.get("age_group"),
            country=row.get("country", "EU"),
            serious=bool(row.get("serious", False)),
            outcome=row.get("outcome"),
            narrative=row.get("narrative"),
          )
        )
        cases_ins += 1
      elif not existing_case.source_region:
        existing_case.source_region = "EU"

      existing_ev = session.scalar(
        select(PvDrugEvent).where(
          PvDrugEvent.case_id == case_id,
          PvDrugEvent.drug_id == drug_id,
          PvDrugEvent.ae_term_id == ae_id,
        )
      )
      if existing_ev is None:
        session.add(
          PvDrugEvent(
            case_id=case_id,
            drug_id=drug_id,
            ae_term_id=ae_id,
            drug_role="PS",
            dose_text=row.get("dose_text"),
          )
        )
        events_ins += 1
  session.commit()
  return {"eu_cases_inserted": cases_ins, "eu_events_inserted": events_ins}


def ingest_meddra_codes(session: Session, payload: dict[str, Any]) -> dict:
  """payload: {ae_term_id: {meddra_pt_code, pt_string?, soc?}}"""
  updated = missing = 0
  for ae_id, row in (payload or {}).items():
    ae = session.get(AeTerm, ae_id)
    if ae is None and row.get("pt_string"):
      ae = session.scalar(select(AeTerm).where(AeTerm.pt_string == row["pt_string"]))
    if ae is None:
      missing += 1
      continue
    if row.get("meddra_pt_code"):
      ae.meddra_pt_code = str(row["meddra_pt_code"])
    if row.get("soc"):
      ae.soc = row["soc"]
    updated += 1
  session.commit()
  return {"meddra_updated": updated, "meddra_missing": missing}


def _parse_date(raw: str | None):
  if not raw:
    return None
  try:
    y, m, d = raw.split("-")
    return date(int(y), int(m), int(d))
  except Exception:  # noqa: BLE001
    return None
