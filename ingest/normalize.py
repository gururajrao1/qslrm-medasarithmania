"""Normalization helpers for ontology keys."""

from __future__ import annotations

import hashlib
import re


def slug(text: str, *, max_len: int = 48) -> str:
  s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
  return s[:max_len] or "unknown"


def ae_term_id_from_pt(pt_string: str) -> str:
  return f"ae_{slug(pt_string)}"


def target_id_from_symbol(gene_symbol: str) -> str:
  return f"tgt_{slug(gene_symbol)}"


def pathway_id_from_source(source_id: str, name: str) -> str:
  if source_id:
    return f"pw_{slug(source_id)}"
  digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
  return f"pw_{digest}"


def variant_id_from_rsid(rsid: str | None, gene: str, clinvar_id: str | None) -> str:
  if rsid:
    return f"var_{slug(rsid)}"
  if clinvar_id:
    return f"var_cv_{slug(clinvar_id)}"
  return f"var_{slug(gene)}_{hashlib.sha1((gene + str(clinvar_id)).encode()).hexdigest()[:8]}"


def to_nm(value: float, units: str | None) -> float | None:
  if value is None:
    return None
  u = (units or "nM").strip().lower()
  if u in {"nm", "nanomolar"}:
    return float(value)
  if u in {"um", "µm", "micromolar", "uM".lower()}:
    return float(value) * 1000.0
  if u in {"mm", "millimolar"}:
    return float(value) * 1_000_000.0
  if u in {"m", "molar"}:
    return float(value) * 1e9
  return float(value)
