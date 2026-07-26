"""Literature evidence + label-side-effect ingest (SIDER / OnSIDES / openFDA SPL).

Offline fixtures under tests/fixtures/phase1; live clients in ingest.sources.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ingest.normalize import ae_term_id_from_pt
from qslrm_erd.models import AeTerm, LiteratureEvidence, SideEffectLabel


def _ensure_ae(session: Session, pt: str) -> str:
  pt = (pt or "").strip()
  if not pt:
    raise ValueError("empty AE preferred term")
  with session.no_autoflush:
    existing = session.scalar(select(AeTerm).where(AeTerm.pt_string == pt))
    if existing:
      return existing.ae_term_id
    ae_id = ae_term_id_from_pt(pt)
    by_id = session.get(AeTerm, ae_id)
    if by_id:
      # same slug, different casing already stored — reuse
      return by_id.ae_term_id
    session.add(
      AeTerm(
        ae_term_id=ae_id,
        pt_string=pt,
        meddra_pt_code=None,
        soc=None,
        snomed_id=None,
        hpo_id=None,
        source="openfda_pt",
      )
    )
    session.flush()
    return ae_id


def ingest_literature(session: Session, payload: dict[str, Any]) -> dict:
  """payload: {drug_id: [{pmid, title, ae, year, source, citations, snippet, confirmed, extractor}]}"""
  inserted = updated = 0
  for drug_id, rows in (payload or {}).items():
    for row in rows or []:
      ae_id = _ensure_ae(session, row["ae"])
      source = row.get("source", "pubmed")
      pmid = str(row["pmid"])
      existing = session.scalar(
        select(LiteratureEvidence).where(
          LiteratureEvidence.drug_id == drug_id,
          LiteratureEvidence.ae_term_id == ae_id,
          LiteratureEvidence.pmid == pmid,
          LiteratureEvidence.source == source,
        )
      )
      data = dict(
        drug_id=drug_id,
        ae_term_id=ae_id,
        pmid=pmid,
        title=row["title"],
        year=row.get("year"),
        source=source,
        citation_count=row.get("citations"),
        abstract_snippet=row.get("snippet"),
        relation_confirmed=bool(row.get("confirmed", True)),
        extractor=row.get("extractor", "fixture"),
      )
      if existing is None:
        session.add(LiteratureEvidence(**data))
        inserted += 1
      else:
        for k, v in data.items():
          setattr(existing, k, v)
        updated += 1
  session.commit()
  return {"lit_inserted": inserted, "lit_updated": updated}


def ingest_label_effects(session: Session, payload: dict[str, Any], *, default_source: str = "sider") -> dict:
  """payload: {drug_id: [{ae, frequency, source?}]} — SIDER / OnSIDES / openFDA SPL / OT LRT."""
  inserted = updated = 0
  for drug_id, rows in (payload or {}).items():
    for row in rows or []:
      ae_id = _ensure_ae(session, row["ae"])
      source = row.get("source", default_source)
      existing = session.scalar(
        select(SideEffectLabel).where(
          SideEffectLabel.drug_id == drug_id,
          SideEffectLabel.ae_term_id == ae_id,
          SideEffectLabel.source == source,
        )
      )
      data = dict(
        drug_id=drug_id,
        ae_term_id=ae_id,
        frequency=row.get("frequency", "postmarketing"),
        source=source,
      )
      if existing is None:
        session.add(SideEffectLabel(**data))
        inserted += 1
      else:
        for k, v in data.items():
          setattr(existing, k, v)
        updated += 1
  session.commit()
  return {f"{default_source}_inserted": inserted, f"{default_source}_updated": updated}


def ingest_sider(session: Session, payload: dict[str, Any]) -> dict:
  return ingest_label_effects(session, payload, default_source="sider")


def ingest_onsides(session: Session, payload: dict[str, Any]) -> dict:
  """OnSIDES — PubMedBERT-extracted ADEs from US/EU/UK/JP labels (Tatonetti lab)."""
  return ingest_label_effects(session, payload, default_source="onsides")


def ingest_opentargets_pv(session: Session, payload: dict[str, Any]) -> dict:
  """Open Targets FAERS LRT significant adverse events (fixtures or live GraphQL)."""
  return ingest_label_effects(session, payload, default_source="opentargets_pv")


def ingest_openfda_spl(session: Session, payload: dict[str, Any]) -> dict:
  """openFDA Structured Product Labeling adverse/warning matches."""
  return ingest_label_effects(session, payload, default_source="openfda_spl")
