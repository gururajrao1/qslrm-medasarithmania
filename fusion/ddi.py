"""DDI risk matrix from CYP substrate overlaps (PharmGKB/DrugBank-style)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from qslrm_erd.models import DdiRisk, Drug, TrialConcomitant

NARROW_TI = frozenset(
  {
    "warfarin",
    "phenytoin",
    "carbamazepine",
    "digoxin",
    "lithium",
    "tacrolimus",
    "cyclosporine",
    "sirolimus",
    "theophylline",
  }
)

MAJOR_ENZYMES = frozenset({"CYP3A4", "CYP2D6"})


def _is_narrow_ti(name: str | None) -> bool:
  return bool(name) and name.strip().lower() in NARROW_TI


def assess_ddi(
  concomitant_name: str | None, enzyme: str, drug_is_narrow_ti: bool = False
) -> dict[str, object]:
  """Severity triage for one CYP overlap (labels, not clinical advice)."""
  level = "high" if enzyme.upper() in MAJOR_ENZYMES else "moderate"
  narrow = _is_narrow_ti(concomitant_name) or drug_is_narrow_ti
  if narrow and level == "moderate":
    level = "high"
  severity = "major" if (level == "high" and narrow) else ("moderate" if level == "high" else "minor")
  guidance = (
    f"{enzyme} overlap"
    + (" with narrow-therapeutic-index exposure" if narrow else "")
    + " — review concomitant dosing and monitoring; not a contraindication."
  )
  return {"level": level, "severity": severity, "narrow_ti": narrow, "guidance": guidance}


def concomitant_case_count(session: Session, concomitant_name: str | None) -> int:
  """PV link count for the concomitant when it resolves to a known drug."""
  if not concomitant_name:
    return 0
  from qslrm_erd.models import PvDrugEvent

  name = concomitant_name.strip().lower()
  drug_ids = [
    d.drug_id
    for d in session.scalars(select(Drug)).all()
    if (d.preferred_name or "").lower() == name or (d.brand_name or "").lower() == name
  ]
  if not drug_ids:
    return 0
  return int(
    session.scalar(
      select(func.count()).select_from(PvDrugEvent).where(PvDrugEvent.drug_id.in_(drug_ids))
    )
    or 0
  )


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
      assessment = assess_ddi(row.concomitant_name, enz, _is_narrow_ti(drug.preferred_name))
      level = str(assessment["level"])
      mech = f"Competitive metabolism via {enz}"
      existing = session.scalar(
        select(DdiRisk).where(
          DdiRisk.drug_id == row.drug_id,
          DdiRisk.concomitant_name == row.concomitant_name,
          DdiRisk.enzyme == enz,
        )
      )
      payload = {
        "drug_id": row.drug_id,
        "concomitant_name": row.concomitant_name,
        "enzyme": enz,
        "risk_level": level,
        "mechanism": mech,
        "notes": f"Trial {row.nct_id} concomitant log · severity {assessment['severity']}",
      }
      if existing is None:
        session.add(DdiRisk(**payload))
        inserted += 1
      else:
        for k, v in payload.items():
          setattr(existing, k, v)
        updated += 1
  session.commit()
  return {"ddi_inserted": inserted, "ddi_updated": updated}
