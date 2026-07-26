"""Compute multi-omic scores including S_trans from LINCS signatures."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from omic_engine.scoring import components_with_engine, soff, sgen, spath, strans, tox_weight_for_tag
from qslrm_erd.models import (
  AeTerm,
  Drug,
  DrugTarget,
  OmicScore,
  Pathway,
  PathwayTarget,
  PvDrugEvent,
  RiskScore,
  SignalStat,
  TranscriptSignature,
  Variant,
)
from qslrm_erd.settings import get_settings


def score_drug_ae(session: Session, *, drug_id: str, ae: AeTerm) -> dict:
  dts = session.scalars(select(DrugTarget).where(DrugTarget.drug_id == drug_id)).all()
  affinities = [float(d.affinity_nm) if d.affinity_nm is not None else 1000.0 for d in dts]
  is_off = [bool(d.is_off_target) for d in dts]
  s_off = soff(affinities, is_off) if dts else 0.0

  target_ids = {d.target_id for d in dts}
  pt_rows = (
    session.execute(
      select(PathwayTarget.pathway_id, Pathway.tox_tag)
      .join(Pathway, Pathway.pathway_id == PathwayTarget.pathway_id)
      .where(PathwayTarget.target_id.in_(target_ids))
    ).all()
    if target_ids
    else []
  )
  seen = set()
  hits: list[bool] = []
  weights: list[float] = []
  for pathway_id, tox_tag in pt_rows:
    if pathway_id in seen:
      continue
    seen.add(pathway_id)
    hits.append(True)
    weights.append(tox_weight_for_tag(tox_tag))
  s_path = spath(hits, weights) if hits else 0.0

  sigs = session.scalars(
    select(TranscriptSignature).where(TranscriptSignature.drug_id == drug_id)
  ).all()
  z_scores = [float(s.z_score) for s in sigs]
  tox_w = [float(s.tox_weight) for s in sigs]
  # mean tox-weighted |z| so LINCS gene count does not dominate S_off / S_gen
  s_trans_val = (strans(z_scores, tox_w) / len(sigs)) if sigs else 0.0

  variants = session.scalars(select(Variant)).all()
  pt = (ae.pt_string or "").strip().lower()
  effects = [float(v.effect_size) if v.effect_size is not None else 0.0 for v in variants]
  mask = [bool(v.related_pt) and (v.related_pt or "").strip().lower() == pt for v in variants]
  s_gen_val = sgen(effects, mask) if variants else 0.0

  comps = components_with_engine(s_off, s_path, s_trans_val, s_gen_val)
  return {
    "drug_id": drug_id,
    "ae_term_id": ae.ae_term_id,
    "s_off": comps.s_off,
    "s_path": comps.s_path,
    "s_trans": comps.s_trans,
    "s_gen": comps.s_gen,
    "omic_risk": comps.omic_risk,
    "engine": comps.engine,
  }


def run_omic_scoring(session: Session, *, prefer_julia: bool = False) -> dict:
  _ = prefer_julia
  settings = get_settings()
  model_version = settings.model_version
  drugs = list(session.scalars(select(Drug.drug_id).where(Drug.is_mvp_seed.is_(True))).all())
  aes = list(session.scalars(select(AeTerm)).all())

  pairs = session.execute(
    select(SignalStat.drug_id, SignalStat.ae_term_id).where(SignalStat.model_version == model_version)
  ).all()
  pair_filter = {(d, a) for d, a in pairs}
  if not pair_filter:
    pairs = session.execute(select(PvDrugEvent.drug_id, PvDrugEvent.ae_term_id).distinct()).all()
    pair_filter = {(d, a) for d, a in pairs}

  inserted = updated = 0
  for drug_id in drugs:
    for ae in aes:
      if (drug_id, ae.ae_term_id) not in pair_filter:
        continue
      row = score_drug_ae(session, drug_id=drug_id, ae=ae)
      existing = session.scalar(
        select(OmicScore).where(
          OmicScore.drug_id == drug_id,
          OmicScore.ae_term_id == ae.ae_term_id,
          OmicScore.model_version == model_version,
        )
      )
      payload = {**row, "model_version": model_version}
      if existing is None:
        session.add(OmicScore(**payload))
        inserted += 1
      else:
        for k, v in payload.items():
          setattr(existing, k, v)
        updated += 1

      rs = session.scalar(
        select(RiskScore).where(
          RiskScore.drug_id == drug_id,
          RiskScore.ae_term_id == ae.ae_term_id,
          RiskScore.model_version == model_version,
        )
      )
      if rs is None:
        session.add(
          RiskScore(
            drug_id=drug_id,
            ae_term_id=ae.ae_term_id,
            n_reports=0,
            omic_risk=row["omic_risk"],
            action_needed=False,
            rising_signal=False,
            model_version=model_version,
          )
        )
      else:
        rs.omic_risk = row["omic_risk"]

  session.commit()
  return {"omic_inserted": inserted, "omic_updated": updated}
