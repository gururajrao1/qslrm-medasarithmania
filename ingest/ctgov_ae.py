"""ClinicalTrials.gov AE/dose/concomitant/onset ingest (fixture + live stub)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ingest import loaders
from ingest.normalize import ae_term_id_from_pt
from qslrm_erd.models import AeTerm, TrialAe, TrialConcomitant, TrialOnsetCurve


def _resolve_ae_id(session: Session, pt: str) -> str:
  """Map PT string to canonical ae_term_id (prefer seed ids over slug)."""
  preferred = ae_term_id_from_pt(pt)
  row = {
    "ae_term_id": preferred,
    "pt_string": pt,
    "meddra_pt_code": None,
    "soc": None,
    "snomed_id": None,
    "hpo_id": None,
    "source": "openfda_pt",
  }
  loaders.upsert_ae_terms(session, [row])
  # upsert_ae_terms rewrites ae_term_id to the seed/canonical PK when PT matches
  return row["ae_term_id"]


def ingest_ctgov(session: Session, payload: dict[str, Any]) -> dict:
  ae_ins = trial_ins = comed_ins = curve_ins = 0
  for drug_id, block in payload.items():
    for trial in block.get("trials") or []:
      nct = trial["nct_id"]
      phase = trial.get("phase")
      for arm in trial.get("arms") or []:
        pt = arm["ae"]
        ae_id = _resolve_ae_id(session, pt)
        ae_ins += 1
        with session.no_autoflush:
          existing = session.scalar(
            select(TrialAe).where(
              TrialAe.nct_id == nct,
              TrialAe.arm == arm["arm"],
              TrialAe.ae_term_id == ae_id,
            )
          )
        row = dict(
          nct_id=nct,
          drug_id=drug_id,
          phase=phase,
          arm=arm["arm"],
          ae_term_id=ae_id,
          event_count=arm.get("event_count"),
          subjects_at_risk=arm.get("subjects_at_risk"),
          dose_text=arm["arm"],
          median_onset_weeks=arm.get("median_onset_weeks"),
        )
        if existing is None:
          session.add(TrialAe(**row))
          trial_ins += 1
        else:
          for k, v in row.items():
            setattr(existing, k, v)

      for c in trial.get("concomitants") or []:
        with session.no_autoflush:
          existing = session.scalar(
            select(TrialConcomitant).where(
              TrialConcomitant.nct_id == nct,
              TrialConcomitant.drug_id == drug_id,
              TrialConcomitant.concomitant_name == c["name"],
            )
          )
        crow = dict(
          nct_id=nct,
          drug_id=drug_id,
          concomitant_name=c["name"],
          concomitant_rxnorm=c.get("rxnorm"),
          cyp_enzymes=c.get("cyp_enzymes"),
        )
        if existing is None:
          session.add(TrialConcomitant(**crow))
          comed_ins += 1
        else:
          for k, v in crow.items():
            setattr(existing, k, v)

      onset = trial.get("onset_curve") or {}
      if onset:
        ae_id = _resolve_ae_id(session, onset["ae"])
        for p in onset.get("points") or []:
          week = float(p["week"])
          surv = float(p["survival_prob"])
          with session.no_autoflush:
            existing = session.scalar(
              select(TrialOnsetCurve).where(
                TrialOnsetCurve.drug_id == drug_id,
                TrialOnsetCurve.ae_term_id == ae_id,
                TrialOnsetCurve.week == week,
                TrialOnsetCurve.nct_id == nct,
              )
            )
          orow = dict(
            drug_id=drug_id,
            ae_term_id=ae_id,
            nct_id=nct,
            week=week,
            survival_prob=surv,
            event_prob=1.0 - surv,
          )
          if existing is None:
            session.add(TrialOnsetCurve(**orow))
            curve_ins += 1
          else:
            for k, v in orow.items():
              setattr(existing, k, v)

  session.commit()
  return {
    "trial_ae_upserts": trial_ins,
    "concomitants": comed_ins,
    "onset_points": curve_ins,
    "ae_touched": ae_ins,
  }
