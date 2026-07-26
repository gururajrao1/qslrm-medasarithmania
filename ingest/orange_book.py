"""Orange Book–style regulatory hygiene for MVP drugs (fixtures)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from qslrm_erd.models import Drug


def ingest_orange_book(session: Session, payload: dict[str, Any]) -> dict:
  """payload: {drug_id: {nda_bla, applicant, molecule_type, trade_name, ...}}"""
  updated = skipped = 0
  for drug_id, row in (payload or {}).items():
    drug = session.get(Drug, drug_id)
    if drug is None:
      skipped += 1
      continue
    if row.get("nda_bla"):
      drug.nda_bla = row["nda_bla"]
    if row.get("applicant"):
      drug.sponsor_company = row["applicant"]
    if row.get("molecule_type"):
      drug.molecule_type = row["molecule_type"]
    if row.get("trade_name") and not drug.brand_name:
      drug.brand_name = row["trade_name"]
    note = f"Orange Book {row.get('nda_bla')} ({row.get('approval_year')})"
    if drug.notes and "Orange Book" not in drug.notes:
      drug.notes = f"{drug.notes}; {note}"
    elif not drug.notes:
      drug.notes = note
    updated += 1
  session.commit()
  return {"orange_book_updated": updated, "orange_book_skipped": skipped}
