"""WHO ICTRP/CTRI, MedDRA hierarchy, Synthea onset, FAERS quarterly helpers."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ingest.ctgov_ae import _resolve_ae_id
from ingest.literature import _ensure_ae
from qslrm_erd.models import (
  AeTerm,
  OntologyCrosswalk,
  PvCase,
  PvDrugEvent,
  TrialAe,
  TrialOnsetCurve,
)


def ingest_meddra_hierarchy(session: Session, payload: dict[str, Any]) -> dict:
  """Apply SOC ↔ HLT ↔ PT hierarchy onto ae_term + ontology_crosswalk.

  payload: {
    ae_map: {ae_term_id|pt_string: {pt_code, hlt, hlt_code, soc, soc_code}},
    nodes?: [{code, term, level, parent_code}]
  }
  """
  updated = crosswalks = missing = 0
  ae_map = (payload or {}).get("ae_map") or payload or {}
  # Allow flat {ae_id: {...}} or nested ae_map
  if "ae_map" in (payload or {}):
    ae_map = payload["ae_map"]

  for key, row in ae_map.items():
    if key in {"ae_map", "nodes"}:
      continue
    ae = session.get(AeTerm, key)
    if ae is None and row.get("pt_string"):
      ae = session.scalar(select(AeTerm).where(AeTerm.pt_string == row["pt_string"]))
    if ae is None:
      missing += 1
      continue
    if row.get("pt_code") or row.get("meddra_pt_code"):
      ae.meddra_pt_code = str(row.get("pt_code") or row.get("meddra_pt_code"))
    if row.get("hlt"):
      ae.meddra_hlt = row["hlt"]
    if row.get("hlt_code"):
      ae.meddra_hlt_code = str(row["hlt_code"])
    if row.get("soc"):
      ae.soc = row["soc"]
    if row.get("soc_code"):
      ae.meddra_soc_code = str(row["soc_code"])
    updated += 1

    # Strict hierarchical joins via crosswalk
    pt_code = ae.meddra_pt_code
    if pt_code and ae.meddra_hlt_code:
      crosswalks += _upsert_xwalk(
        session,
        entity_type="ae",
        from_system="meddra_pt",
        from_id=pt_code,
        to_system="meddra_hlt",
        to_id=ae.meddra_hlt_code,
      )
    if ae.meddra_hlt_code and ae.meddra_soc_code:
      crosswalks += _upsert_xwalk(
        session,
        entity_type="ae",
        from_system="meddra_hlt",
        from_id=ae.meddra_hlt_code,
        to_system="meddra_soc",
        to_id=ae.meddra_soc_code,
      )
    if pt_code and ae.meddra_soc_code:
      crosswalks += _upsert_xwalk(
        session,
        entity_type="ae",
        from_system="meddra_pt",
        from_id=pt_code,
        to_system="meddra_soc",
        to_id=ae.meddra_soc_code,
      )

  for node in (payload or {}).get("nodes") or []:
    code = str(node.get("code") or "")
    parent = node.get("parent_code")
    level = (node.get("level") or "").upper()
    if not code or not parent:
      continue
    parent_level = "meddra_hlt" if level == "PT" else "meddra_soc"
    child_level = f"meddra_{level.lower()}"
    crosswalks += _upsert_xwalk(
      session,
      entity_type="ae",
      from_system=child_level,
      from_id=code,
      to_system=parent_level if level != "HLT" else "meddra_soc",
      to_id=str(parent),
    )

  session.commit()
  return {"meddra_hier_updated": updated, "meddra_hier_missing": missing, "crosswalks": crosswalks}


def ingest_ictrp_ctri(session: Session, payload: dict[str, Any]) -> dict:
  """WHO ICTRP / CTRI global trial AE arms → trial_ae + Global-region PV stubs.

  payload: {drug_id: {trials: [{registry_id, source, phase, country, arms: [...]}]}}
  """
  trial_ins = cases_ins = events_ins = 0
  for drug_id, block in (payload or {}).items():
    for trial in block.get("trials") or []:
      rid = trial.get("registry_id") or trial.get("nct_id") or "ICTRP-UNKNOWN"
      phase = trial.get("phase")
      source = trial.get("source", "ICTRP")
      country = trial.get("country", "IN")
      for arm in trial.get("arms") or []:
        pt = arm["ae"]
        ae_id = _resolve_ae_id(session, pt)
        arm_name = arm.get("arm") or "experimental"
        existing = session.scalar(
          select(TrialAe).where(
            TrialAe.nct_id == rid,
            TrialAe.arm == arm_name,
            TrialAe.ae_term_id == ae_id,
          )
        )
        row = dict(
          nct_id=rid,
          drug_id=drug_id,
          phase=phase,
          arm=arm_name,
          ae_term_id=ae_id,
          event_count=arm.get("event_count"),
          subjects_at_risk=arm.get("subjects_at_risk"),
          dose_text=arm.get("dose_text") or arm_name,
          median_onset_weeks=arm.get("median_onset_weeks"),
        )
        if existing is None:
          session.add(TrialAe(**row))
          trial_ins += 1
        else:
          for k, v in row.items():
            setattr(existing, k, v)

        # Global PV stub so region=Global filters return rows
        n_cases = int(arm.get("global_cases") or max(3, (arm.get("event_count") or 3) // 2))
        for i in range(n_cases):
          case_id = f"ictrp_{rid}_{ae_id}_{i}".replace("/", "_")[:64]
          if session.get(PvCase, case_id) is None:
            session.add(
              PvCase(
                case_id=case_id,
                source_period=f"{source.lower()}",
                source_region="Global",
                report_date=_parse_date(arm.get("report_date")),
                country=country,
                serious=bool(arm.get("serious", True)),
                narrative=f"{source} registry AE: {pt} ({rid})",
              )
            )
            cases_ins += 1
          if (
            session.scalar(
              select(PvDrugEvent).where(
                PvDrugEvent.case_id == case_id,
                PvDrugEvent.drug_id == drug_id,
                PvDrugEvent.ae_term_id == ae_id,
              )
            )
            is None
          ):
            session.add(
              PvDrugEvent(
                case_id=case_id,
                drug_id=drug_id,
                ae_term_id=ae_id,
                drug_role="PS",
                dose_text=arm.get("dose_text") or arm_name,
              )
            )
            events_ins += 1
  session.commit()
  return {
    "ictrp_trials_inserted": trial_ins,
    "ictrp_cases_inserted": cases_ins,
    "ictrp_events_inserted": events_ins,
  }


def ingest_synthea(session: Session, payload: dict[str, Any]) -> dict:
  """Synthea-style synthetic exposure / time-to-onset → trial_onset_curve.

  payload: {drug_id: {cohorts: [{ae, n_exposed, dose_regimen, median_onset_days, points|onset_curve}]}}
  """
  curve_ins = ae_touch = 0
  for drug_id, block in (payload or {}).items():
    for cohort in block.get("cohorts") or []:
      pt = cohort["ae"]
      ae_id = _ensure_ae(session, pt)
      ae_touch += 1
      nct = cohort.get("cohort_id") or f"synthea_{drug_id}"
      points = cohort.get("points") or (cohort.get("onset_curve") or {}).get("points") or []
      if not points:
        # Default acute t_onset curve (days → weeks)
        med_days = float(cohort.get("median_onset_days") or 7)
        med_w = med_days / 7.0
        points = [
          {"week": 0, "survival_prob": 1.0},
          {"week": round(med_w * 0.5, 2), "survival_prob": 0.75},
          {"week": round(med_w, 2), "survival_prob": 0.5},
          {"week": round(med_w * 2, 2), "survival_prob": 0.35},
          {"week": round(med_w * 4, 2), "survival_prob": 0.25},
        ]
      for p in points:
        week = float(p["week"])
        surv = float(p["survival_prob"])
        existing = session.scalar(
          select(TrialOnsetCurve).where(
            TrialOnsetCurve.drug_id == drug_id,
            TrialOnsetCurve.ae_term_id == ae_id,
            TrialOnsetCurve.nct_id == nct,
            TrialOnsetCurve.week == week,
          )
        )
        row = dict(
          drug_id=drug_id,
          ae_term_id=ae_id,
          nct_id=nct,
          week=week,
          survival_prob=surv,
          event_prob=1.0 - surv,
        )
        if existing is None:
          session.add(TrialOnsetCurve(**row))
          curve_ins += 1
        else:
          for k, v in row.items():
            setattr(existing, k, v)

      # Also stamp median onset on a trial_ae row for UI KM tab
      arm = cohort.get("dose_regimen") or "synthea_exposure"
      existing_ta = session.scalar(
        select(TrialAe).where(
          TrialAe.nct_id == nct,
          TrialAe.arm == arm,
          TrialAe.ae_term_id == ae_id,
        )
      )
      med_w = float(cohort.get("median_onset_days") or 7) / 7.0
      ta = dict(
        nct_id=nct,
        drug_id=drug_id,
        phase="RWE-synthetic",
        arm=arm,
        ae_term_id=ae_id,
        event_count=cohort.get("n_events"),
        subjects_at_risk=cohort.get("n_exposed"),
        dose_text=arm,
        median_onset_weeks=round(med_w, 2),
      )
      if existing_ta is None:
        session.add(TrialAe(**ta))
      else:
        for k, v in ta.items():
          setattr(existing_ta, k, v)
  session.commit()
  return {"synthea_curves_inserted": curve_ins, "synthea_cohorts": ae_touch}


def _upsert_xwalk(
  session: Session,
  *,
  entity_type: str,
  from_system: str,
  from_id: str,
  to_system: str,
  to_id: str,
) -> int:
  existing = session.scalar(
    select(OntologyCrosswalk).where(
      OntologyCrosswalk.entity_type == entity_type,
      OntologyCrosswalk.from_system == from_system,
      OntologyCrosswalk.from_id == from_id,
      OntologyCrosswalk.to_system == to_system,
      OntologyCrosswalk.to_id == to_id,
    )
  )
  if existing is None:
    session.add(
      OntologyCrosswalk(
        entity_type=entity_type,
        from_system=from_system,
        from_id=from_id,
        to_system=to_system,
        to_id=to_id,
        confidence=1.0,
      )
    )
    return 1
  return 0


def _parse_date(raw: str | None):
  if not raw:
    return None
  try:
    y, m, d = raw.split("-")
    return date(int(y), int(m), int(d))
  except Exception:  # noqa: BLE001
    return None
