"""Protocol exclusion optimizer + KM curve helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from fusion.decisions import protocol_exclusion_clause
from qslrm_erd.models import AeTerm, Drug, ProtocolExclusion, RiskScore, Variant
from qslrm_erd.settings import get_settings


def generate_protocol_exclusions(session: Session) -> dict:
  settings = get_settings()
  inserted = 0
  from qslrm_erd.models import OmicScore

  risks = session.scalars(
    select(RiskScore).where(
      RiskScore.model_version == settings.model_version,
      RiskScore.fused_score.is_not(None),
    )
  ).all()
  omics = {
    (o.drug_id, o.ae_term_id): o
    for o in session.scalars(
      select(OmicScore).where(OmicScore.model_version == settings.model_version)
    ).all()
  }
  for rs in risks:
    om = omics.get((rs.drug_id, rs.ae_term_id))
    genetic_mass = max(float(rs.attr_genetic or 0), float(om.s_gen if om else 0) / 5.0)
    if genetic_mass < 0.08 and (not om or (om.s_gen or 0) < 0.4):
      continue
    drug = session.get(Drug, rs.drug_id)
    ae = session.get(AeTerm, rs.ae_term_id)
    variants = session.scalars(
      select(Variant).where(
        Variant.related_pt.is_not(None),
      )
    ).all()
    pt = (ae.pt_string if ae else "").lower()
    matched = [
      v
      for v in variants
      if v.related_pt and v.related_pt.lower() == pt and v.metabolizer_impact
    ]
    if not matched:
      matched = [v for v in variants if v.metabolizer_impact][:1]
    for v in matched[:1]:
      reduction = min(0.8, max(0.4, genetic_mass if genetic_mass >= 0.4 else 0.55))
      clause, rationale = protocol_exclusion_clause(
        drug_name=drug.preferred_name if drug else rs.drug_id,
        pt_string=ae.pt_string if ae else rs.ae_term_id,
        gene_symbol=v.gene_symbol,
        metabolizer_impact=v.metabolizer_impact,
        estimated_reduction=reduction,
      )
      existing = session.scalar(
        select(ProtocolExclusion).where(
          ProtocolExclusion.drug_id == rs.drug_id,
          ProtocolExclusion.ae_term_id == rs.ae_term_id,
          ProtocolExclusion.variant_id == v.variant_id,
        )
      )
      if existing is None:
        session.add(
          ProtocolExclusion(
            drug_id=rs.drug_id,
            ae_term_id=rs.ae_term_id,
            variant_id=v.variant_id,
            clause_text=clause,
            rationale=rationale,
            estimated_adr_reduction=reduction,
          )
        )
        inserted += 1
      else:
        existing.clause_text = clause
        existing.rationale = rationale
        existing.estimated_adr_reduction = reduction
  session.commit()
  return {"protocol_exclusions": inserted}
