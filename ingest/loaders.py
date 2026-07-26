"""DB upsert loaders for Phase 1 ingest outputs."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from qslrm_erd.models import (
  AeTerm,
  DrugTarget,
  OntologyCrosswalk,
  Pathway,
  PathwayTarget,
  PvCase,
  PvDrugEvent,
  Target,
  Variant,
)


def upsert_by_pk(session: Session, model, rows: list[dict], pk: str) -> tuple[int, int]:
  inserted = updated = 0
  for row in rows:
    existing = session.get(model, row[pk])
    if existing is None:
      session.add(model(**row))
      inserted += 1
    else:
      for k, v in row.items():
        if v is not None:
          setattr(existing, k, v)
      updated += 1
  return inserted, updated


def upsert_targets(session: Session, rows: list[dict]) -> tuple[int, int]:
  return upsert_by_pk(session, Target, rows, "target_id")


def upsert_pathways(session: Session, rows: list[dict]) -> tuple[int, int]:
  return upsert_by_pk(session, Pathway, rows, "pathway_id")


def upsert_variants(session: Session, rows: list[dict]) -> tuple[int, int]:
  return upsert_by_pk(session, Variant, rows, "variant_id")


def upsert_ae_terms(session: Session, rows: list[dict]) -> tuple[int, int]:
  inserted = updated = 0
  with session.no_autoflush:
    for row in rows:
      existing = session.scalar(select(AeTerm).where(AeTerm.pt_string == row["pt_string"]))
      if existing is None:
        existing = session.get(AeTerm, row["ae_term_id"])
      if existing is None:
        session.add(AeTerm(**row))
        inserted += 1
      else:
        # never rewrite pt_string (unique); only fill missing ontology fields
        for k in (
          "meddra_pt_code",
          "meddra_hlt",
          "meddra_hlt_code",
          "meddra_soc_code",
          "soc",
          "snomed_id",
          "hpo_id",
          "source",
        ):
          v = row.get(k)
          if v is not None and getattr(existing, k, None) in (None, "", "openfda_pt"):
            if k == "source" and existing.source and existing.source != "openfda_pt":
              continue
            if k == "source":
              continue  # keep original source
            setattr(existing, k, v)
        row["ae_term_id"] = existing.ae_term_id
        updated += 1
  return inserted, updated


def upsert_pv_cases(session: Session, rows: list[dict]) -> tuple[int, int]:
  return upsert_by_pk(session, PvCase, rows, "case_id")


def upsert_drug_targets(session: Session, rows: list[dict]) -> tuple[int, int]:
  inserted = updated = 0
  for row in rows:
    existing = session.scalar(
      select(DrugTarget).where(
        DrugTarget.drug_id == row["drug_id"],
        DrugTarget.target_id == row["target_id"],
      )
    )
    if existing is None:
      session.add(DrugTarget(**row))
      inserted += 1
    else:
      for k, v in row.items():
        if v is not None:
          setattr(existing, k, v)
      # chembl source should win over seed when affinities present
      if row.get("source") == "chembl":
        existing.source = "chembl"
      updated += 1
  return inserted, updated


def upsert_pathway_targets(session: Session, rows: list[dict]) -> tuple[int, int]:
  inserted = updated = 0
  for row in rows:
    existing = session.scalar(
      select(PathwayTarget).where(
        PathwayTarget.pathway_id == row["pathway_id"],
        PathwayTarget.target_id == row["target_id"],
      )
    )
    if existing is None:
      session.add(PathwayTarget(**row))
      inserted += 1
    else:
      updated += 1
  return inserted, updated


def upsert_pv_drug_events(session: Session, rows: list[dict]) -> tuple[int, int]:
  inserted = updated = 0
  for row in rows:
    existing = session.scalar(
      select(PvDrugEvent).where(
        PvDrugEvent.case_id == row["case_id"],
        PvDrugEvent.drug_id == row["drug_id"],
        PvDrugEvent.ae_term_id == row["ae_term_id"],
      )
    )
    if existing is None:
      session.add(PvDrugEvent(**row))
      inserted += 1
    else:
      for k, v in row.items():
        if v is not None:
          setattr(existing, k, v)
      updated += 1
  return inserted, updated


def upsert_crosswalks(session: Session, rows: list[dict]) -> tuple[int, int]:
  inserted = updated = 0
  for row in rows:
    existing = session.scalar(
      select(OntologyCrosswalk).where(
        OntologyCrosswalk.entity_type == row["entity_type"],
        OntologyCrosswalk.from_system == row["from_system"],
        OntologyCrosswalk.from_id == row["from_id"],
        OntologyCrosswalk.to_system == row["to_system"],
        OntologyCrosswalk.to_id == row["to_id"],
      )
    )
    if existing is None:
      session.add(OntologyCrosswalk(**row))
      inserted += 1
    else:
      existing.confidence = row.get("confidence", existing.confidence)
      updated += 1
  return inserted, updated
