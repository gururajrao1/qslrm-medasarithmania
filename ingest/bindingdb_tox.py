"""BindingDB-style affinity rows + Tox21 assay flags (fixtures)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from qslrm_erd.models import DrugTarget


def ingest_bindingdb(session: Session, payload: dict[str, Any]) -> dict:
  """payload: {drug_id: [{target_id, affinity_nm, is_off_target, action_type}]}"""
  inserted = updated = 0
  for drug_id, rows in (payload or {}).items():
    for row in rows or []:
      existing = session.scalar(
        select(DrugTarget).where(
          DrugTarget.drug_id == drug_id,
          DrugTarget.target_id == row["target_id"],
        )
      )
      data = dict(
        drug_id=drug_id,
        target_id=row["target_id"],
        affinity_nm=row.get("affinity_nm"),
        affinity_type=row.get("affinity_type", "IC50"),
        action_type=row.get("action_type", "inhibitor"),
        is_off_target=bool(row.get("is_off_target", True)),
        source="bindingdb",
      )
      if existing is None:
        session.add(DrugTarget(**data))
        inserted += 1
      else:
        # only overwrite if BindingDB is tighter (lower nM) or missing
        if row.get("affinity_nm") is not None:
          if existing.affinity_nm is None or float(row["affinity_nm"]) < float(existing.affinity_nm):
            existing.affinity_nm = row["affinity_nm"]
            existing.affinity_type = data["affinity_type"]
            existing.source = "bindingdb"
        updated += 1
  session.commit()
  return {"bindingdb_inserted": inserted, "bindingdb_updated": updated}


def ingest_tox21(session: Session, payload: dict[str, Any]) -> dict:
  """Store Tox21 assay hits as transcript_signature tox weights (proxy channel).

  payload: {drug_id: [{assay, active, score}]}
  Maps assay → synthetic gene_symbol tox markers for S_trans enrichment.
  """
  from qslrm_erd.models import TranscriptSignature

  inserted = updated = 0
  for drug_id, rows in (payload or {}).items():
    for row in rows or []:
      if not row.get("active"):
        continue
      gene = f"TOX21_{str(row['assay']).upper()[:24]}"
      existing = session.scalar(
        select(TranscriptSignature).where(
          TranscriptSignature.drug_id == drug_id,
          TranscriptSignature.gene_symbol == gene,
          TranscriptSignature.source == "tox21",
        )
      )
      z = float(row.get("score") or 2.0)
      data = dict(
        drug_id=drug_id,
        gene_symbol=gene,
        z_score=z,
        tox_weight=min(1.5, abs(z) / 2.0),
        direction="up" if z >= 0 else "down",
        source="tox21",
      )
      if existing is None:
        session.add(TranscriptSignature(**data))
        inserted += 1
      else:
        for k, v in data.items():
          setattr(existing, k, v)
        updated += 1
  session.commit()
  return {"tox21_inserted": inserted, "tox21_updated": updated}


def ingest_depmap(session: Session, payload: dict[str, Any]) -> dict:
  """DepMap essentiality as transcript markers (gene dependency proxy)."""
  from qslrm_erd.models import TranscriptSignature

  inserted = updated = 0
  for drug_id, rows in (payload or {}).items():
    for row in rows or []:
      gene = row["gene_symbol"]
      existing = session.scalar(
        select(TranscriptSignature).where(
          TranscriptSignature.drug_id == drug_id,
          TranscriptSignature.gene_symbol == gene,
          TranscriptSignature.source == "depmap",
        )
      )
      # DepMap chronos scores are more negative = more essential
      chronos = float(row.get("chronos") or -0.5)
      z = -chronos * 2.0
      data = dict(
        drug_id=drug_id,
        gene_symbol=gene,
        z_score=z,
        tox_weight=min(1.2, abs(chronos)),
        direction="down",
        source="depmap",
      )
      if existing is None:
        session.add(TranscriptSignature(**data))
        inserted += 1
      else:
        for k, v in data.items():
          setattr(existing, k, v)
        updated += 1
  session.commit()
  return {"depmap_inserted": inserted, "depmap_updated": updated}
