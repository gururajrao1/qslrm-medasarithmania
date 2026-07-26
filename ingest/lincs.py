"""LINCS L1000 fixture / API-stub ingest → transcript_signature."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ingest import loaders
from qslrm_erd.models import TranscriptSignature


def build_transcript_rows(drug_id: str, genes: list[dict]) -> list[dict]:
  rows = []
  for g in genes:
    rows.append(
      {
        "drug_id": drug_id,
        "gene_symbol": g["gene_symbol"].upper(),
        "z_score": float(g["z_score"]),
        "tox_weight": float(g.get("tox_weight", 1.0)),
        "direction": g.get("direction"),
        "source": g.get("source", "lincs_fixture"),
      }
    )
  return rows


def upsert_transcripts(session: Session, rows: list[dict]) -> tuple[int, int]:
  from sqlalchemy import select

  inserted = updated = 0
  for row in rows:
    existing = session.scalar(
      select(TranscriptSignature).where(
        TranscriptSignature.drug_id == row["drug_id"],
        TranscriptSignature.gene_symbol == row["gene_symbol"],
        TranscriptSignature.source == row["source"],
      )
    )
    if existing is None:
      session.add(TranscriptSignature(**row))
      inserted += 1
    else:
      for k, v in row.items():
        setattr(existing, k, v)
      updated += 1
  return inserted, updated


def ingest_lincs(session: Session, payload: dict[str, Any]) -> dict:
  ins = upd = 0
  for drug_id, genes in payload.items():
    rows = build_transcript_rows(drug_id, genes)
    i, u = upsert_transcripts(session, rows)
    ins += i
    upd += u
  session.commit()
  return {"transcript_ins": ins, "transcript_upd": upd}
