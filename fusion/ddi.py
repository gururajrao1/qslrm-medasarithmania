"""DDI risk matrix from CYP substrate overlaps (PharmGKB/DrugBank-style)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from qslrm_erd.models import DdiRisk, Drug, TrialConcomitant


def compute_ddi_risks(session: Session) -> dict:
  inserted = updated = 0
  drugs = {d.drug_id: d for d in session.scalars(select(Drug)).all()}
  comeds = session.scalars(select(TrialConcomitant)).all()
  for row in comeds:
    drug = drugs.get(row.drug_id)
    if not drug:
      continue
    drug_cyps = {x.strip().upper() for x in (drug.cyp_substrates or "").split(",") if x.strip()}
    comed_cyps = {x.strip().upper() for x in (row.cyp_enzymes or "").split(",") if x.strip()}
    overlap = drug_cyps & comed_cyps
    for enz in overlap:
      level = "high" if enz in {"CYP3A4", "CYP2D6"} else "moderate"
      mech = f"Competitive metabolism via {enz}"
      existing = session.scalar(
        select(DdiRisk).where(
          DdiRisk.drug_id == row.drug_id,
          DdiRisk.concomitant_name == row.concomitant_name,
          DdiRisk.enzyme == enz,
        )
      )
      payload = dict(
        drug_id=row.drug_id,
        concomitant_name=row.concomitant_name,
        enzyme=enz,
        risk_level=level,
        mechanism=mech,
        notes=f"Trial {row.nct_id} concomitant log",
      )
      if existing is None:
        session.add(DdiRisk(**payload))
        inserted += 1
      else:
        for k, v in payload.items():
          setattr(existing, k, v)
        updated += 1
  session.commit()
  return {"ddi_inserted": inserted, "ddi_updated": updated}
