"""QC report for Phase 0/1/2 gates."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from qslrm_erd.models import (
  AeTerm,
  DdiRisk,
  DemographicSignal,
  Drug,
  DrugTarget,
  GroundTruthLabel,
  NarrativeEntity,
  OmicScore,
  OntologyCrosswalk,
  Pathway,
  PathwayTarget,
  ProtocolExclusion,
  PvCase,
  PvDrugEvent,
  RiskScore,
  SignalStat,
  SignalVelocity,
  Target,
  TranscriptSignature,
  TrialOnsetCurve,
  Variant,
)
from qslrm_erd.settings import get_settings


def _count(session: Session, model) -> int:
  return int(session.scalar(select(func.count()).select_from(model)) or 0)


def build_qc_report(session: Session) -> dict:
  settings = get_settings()
  n_drugs = _count(session, Drug)
  n_mvp = int(
    session.scalar(select(func.count()).select_from(Drug).where(Drug.is_mvp_seed.is_(True))) or 0
  )
  drugs_missing_chembl = session.scalars(
    select(Drug.preferred_name).where(Drug.chembl_id.is_(None), Drug.is_mvp_seed.is_(True))
  ).all()
  drugs_missing_rxnorm = session.scalars(
    select(Drug.preferred_name).where(Drug.rxnorm_cui.is_(None), Drug.is_mvp_seed.is_(True))
  ).all()

  report = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "mvp_drug_class": settings.mvp_drug_class,
    "model_version": settings.model_version,
    "counts": {
      "drug": n_drugs,
      "drug_mvp": n_mvp,
      "target": _count(session, Target),
      "drug_target": _count(session, DrugTarget),
      "pathway": _count(session, Pathway),
      "pathway_target": _count(session, PathwayTarget),
      "variant": _count(session, Variant),
      "ae_term": _count(session, AeTerm),
      "ontology_crosswalk": _count(session, OntologyCrosswalk),
      "pv_case": _count(session, PvCase),
      "pv_drug_event": _count(session, PvDrugEvent),
      "ground_truth_label": _count(session, GroundTruthLabel),
      "signal_stat": _count(session, SignalStat),
      "omic_score": _count(session, OmicScore),
      "risk_score": _count(session, RiskScore),
      "transcript_signature": _count(session, TranscriptSignature),
      "trial_onset_curve": _count(session, TrialOnsetCurve),
      "ddi_risk": _count(session, DdiRisk),
      "signal_velocity": _count(session, SignalVelocity),
      "demographic_signal": _count(session, DemographicSignal),
      "narrative_entity": _count(session, NarrativeEntity),
      "protocol_exclusion": _count(session, ProtocolExclusion),
    },
    "checks": {
      "mvp_drugs_have_chembl": len(drugs_missing_chembl) == 0,
      "mvp_drugs_have_rxnorm": len(drugs_missing_rxnorm) == 0,
      "has_drug_targets": _count(session, DrugTarget) > 0,
      "has_ae_terms": _count(session, AeTerm) > 0,
      "has_ground_truth": _count(session, GroundTruthLabel) > 0,
      "has_crosswalks": _count(session, OntologyCrosswalk) > 0,
      "phase1_has_faers": _count(session, PvDrugEvent) > 0,
      "phase1_has_variants": _count(session, Variant) >= 2,
      "phase1_has_lincs": _count(session, TranscriptSignature) > 0,
      "phase1_has_onset": _count(session, TrialOnsetCurve) > 0,
      "phase2_has_signals": _count(session, SignalStat) > 0,
      "phase2_has_omic": _count(session, OmicScore) > 0,
      "phase2_has_velocity": _count(session, SignalVelocity) > 0,
      "phase2_has_demographics": _count(session, DemographicSignal) > 0,
      "phase2_risk_seeded": _count(session, RiskScore) > 0,
      "phase3_has_fused": int(
        session.scalar(
          select(func.count()).select_from(RiskScore).where(RiskScore.fused_score.is_not(None))
        )
        or 0
      )
      > 0,
      "phase3_has_attribution": int(
        session.scalar(
          select(func.count())
          .select_from(RiskScore)
          .where(
            RiskScore.attr_dose.is_not(None),
            RiskScore.attr_offtarget.is_not(None),
            RiskScore.attr_transcriptomic.is_not(None),
            RiskScore.attr_genetic.is_not(None),
          )
        )
        or 0
      )
      > 0,
      "phase3_has_ddi": _count(session, DdiRisk) > 0,
    },
    "missing": {
      "chembl": drugs_missing_chembl,
      "rxnorm": drugs_missing_rxnorm,
    },
  }
  report["phase0_pass"] = all(
    [
      report["checks"]["mvp_drugs_have_chembl"],
      report["checks"]["mvp_drugs_have_rxnorm"],
      report["checks"]["has_drug_targets"],
      report["checks"]["has_ae_terms"],
      report["checks"]["has_ground_truth"],
      report["checks"]["has_crosswalks"],
      n_mvp >= 8,
    ]
  )
  report["phase1_pass"] = report["phase0_pass"] and all(
    [
      report["checks"]["phase1_has_faers"],
      report["checks"]["phase1_has_variants"],
      report["counts"]["drug_target"] >= n_mvp,
      report["counts"]["pathway"] >= 1,
    ]
  )
  report["phase2_pass"] = report["phase1_pass"] and all(
    [
      report["checks"]["phase2_has_signals"],
      report["checks"]["phase2_has_omic"],
      report["checks"]["phase2_risk_seeded"],
    ]
  )
  report["phase3_pass"] = report["phase2_pass"] and all(
    [
      report["checks"]["phase3_has_fused"],
      report["checks"]["phase3_has_attribution"],
    ]
  )
  report["modules_pass"] = all(
    [
      report["checks"].get("phase1_has_lincs", False),
      report["checks"].get("phase1_has_onset", False),
      report["checks"].get("phase2_has_velocity", False),
      report["checks"].get("phase2_has_demographics", False),
      report["checks"].get("phase3_has_ddi", False),
    ]
  )
  return report


def write_qc_report(session: Session, path: Path | None = None) -> Path:
  settings = get_settings()
  out = path or Path(settings.processed_data_dir) / "qc_report.json"
  out.parent.mkdir(parents=True, exist_ok=True)
  report = build_qc_report(session)
  out.write_text(json.dumps(report, indent=2), encoding="utf-8")
  return out
