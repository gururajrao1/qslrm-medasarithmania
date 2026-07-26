"""Seed qslrm_erd with kinase MVP dictionary + crosswalks + BBW labels."""

from __future__ import annotations

import argparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from qslrm_erd.db import get_engine
from qslrm_erd.models import (
  AeTerm,
  Drug,
  DrugTarget,
  GroundTruthLabel,
  OntologyCrosswalk,
  Pathway,
  PathwayTarget,
  Target,
  Variant,
)
from qslrm_erd.seeds import kinase_mvp as seed
from qslrm_erd.seeds import sponsor_portfolio as portfolio


def _merged_lists() -> dict[str, list]:
  """Kinase MVP + sponsor portfolio fill (every dropdown sponsor has ≥1 drug)."""
  return {
    "drugs": [*seed.drugs, *portfolio.drugs],
    "targets": [*seed.targets, *portfolio.targets],
    "ae_terms": [*seed.ae_terms, *portfolio.ae_terms],
    "drug_targets": [*seed.drug_targets, *portfolio.drug_targets],
    "crosswalks": [*seed.crosswalks, *portfolio.crosswalks],
    "ground_truth": [*seed.ground_truth, *portfolio.ground_truth],
    "pathways": seed.pathways,
    "pathway_targets": seed.pathway_targets,
    "variants": seed.variants,
  }


def _upsert_rows(session: Session, model, rows: list[dict], pk: str) -> int:
  inserted = 0
  for row in rows:
    existing = session.get(model, row[pk])
    if existing is None:
      session.add(model(**row))
      inserted += 1
    else:
      for key, value in row.items():
        setattr(existing, key, value)
  return inserted


def seed_all(session: Session) -> dict[str, int]:
  data = _merged_lists()
  counts = {
    "drug": _upsert_rows(session, Drug, data["drugs"], "drug_id"),
    "target": _upsert_rows(session, Target, data["targets"], "target_id"),
    "pathway": _upsert_rows(session, Pathway, data["pathways"], "pathway_id"),
    "variant": _upsert_rows(session, Variant, data["variants"], "variant_id"),
    "ae_term": _upsert_rows(session, AeTerm, data["ae_terms"], "ae_term_id"),
  }

  dt_inserted = 0
  for row in data["drug_targets"]:
    exists = session.scalar(
      select(DrugTarget.id).where(
        DrugTarget.drug_id == row["drug_id"],
        DrugTarget.target_id == row["target_id"],
      )
    )
    if exists is None:
      session.add(DrugTarget(**row))
      dt_inserted += 1
  counts["drug_target"] = dt_inserted

  pt_inserted = 0
  for row in data["pathway_targets"]:
    exists = session.scalar(
      select(PathwayTarget.id).where(
        PathwayTarget.pathway_id == row["pathway_id"],
        PathwayTarget.target_id == row["target_id"],
      )
    )
    if exists is None:
      session.add(PathwayTarget(**row))
      pt_inserted += 1
  counts["pathway_target"] = pt_inserted

  # Explicit seed crosswalks + derived ontology maps (Phase 0 key lockdown)
  derived: list[dict] = []
  for d in data["drugs"]:
    if d.get("rxnorm_cui") and d.get("chembl_id"):
      derived.append(
        {
          "entity_type": "drug",
          "from_system": "rxnorm",
          "from_id": d["rxnorm_cui"],
          "to_system": "chembl",
          "to_id": d["chembl_id"],
          "confidence": 1.0,
        }
      )
  for t in data["targets"]:
    if t.get("uniprot_id") and t.get("ensembl_id"):
      derived.append(
        {
          "entity_type": "target",
          "from_system": "uniprot",
          "from_id": t["uniprot_id"],
          "to_system": "ensembl",
          "to_id": t["ensembl_id"],
          "confidence": 1.0,
        }
      )
    if t.get("uniprot_id") and t.get("gene_symbol"):
      derived.append(
        {
          "entity_type": "target",
          "from_system": "uniprot",
          "from_id": t["uniprot_id"],
          "to_system": "gene_symbol",
          "to_id": t["gene_symbol"],
          "confidence": 1.0,
        }
      )
  for a in data["ae_terms"]:
    derived.append(
      {
        "entity_type": "ae",
        "from_system": "openfda_pt",
        "from_id": a["pt_string"],
        "to_system": "openfda_pt",
        "to_id": a["pt_string"],
        "confidence": 1.0,
      }
    )

  cw_inserted = 0
  seen: set[tuple] = set()
  for row in [*data["crosswalks"], *derived]:
    key = (
      row["entity_type"],
      row["from_system"],
      row["from_id"],
      row["to_system"],
      row["to_id"],
    )
    if key in seen:
      continue
    seen.add(key)
    exists = session.scalar(
      select(OntologyCrosswalk.id).where(
        OntologyCrosswalk.entity_type == row["entity_type"],
        OntologyCrosswalk.from_system == row["from_system"],
        OntologyCrosswalk.from_id == row["from_id"],
        OntologyCrosswalk.to_system == row["to_system"],
        OntologyCrosswalk.to_id == row["to_id"],
      )
    )
    if exists is None:
      session.add(OntologyCrosswalk(**row))
      cw_inserted += 1
  counts["ontology_crosswalk"] = cw_inserted

  gt_inserted = 0
  for row in data["ground_truth"]:
    exists = session.scalar(
      select(GroundTruthLabel.id).where(
        GroundTruthLabel.drug_id == row["drug_id"],
        GroundTruthLabel.ae_term_id == row["ae_term_id"],
        GroundTruthLabel.label_type == row["label_type"],
      )
    )
    if exists is None:
      session.add(GroundTruthLabel(**row))
      gt_inserted += 1
  counts["ground_truth_label"] = gt_inserted

  session.commit()
  return counts


def main() -> None:
  parser = argparse.ArgumentParser(description="Seed QSLRM kinase MVP dictionary")
  parser.parse_args()
  engine = get_engine()
  with Session(engine) as session:
    counts = seed_all(session)
  print("Seed complete:")
  for table, n in counts.items():
    print(f"  {table}: {n} inserted (or 0 if already present / updated)")


if __name__ == "__main__":
  main()
