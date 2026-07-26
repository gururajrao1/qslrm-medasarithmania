"""ChEMBL REST ingest — mechanisms + binding affinities for MVP kinase drugs."""

from __future__ import annotations

from typing import Any

from ingest.http_util import get_json
from ingest.normalize import target_id_from_symbol, to_nm
from qslrm_erd.settings import get_settings

CHEMBL_API = "https://www.ebi.ac.uk/chembl/api/data"
AFFINITY_TYPES = {"IC50", "Ki", "Kd", "EC50"}


def molecule_url(chembl_id: str) -> str:
  return f"{CHEMBL_API}/molecule/{chembl_id}.json"


def _paginate(url: str, params: dict[str, Any], *, limit: int) -> list[dict]:
  rows: list[dict] = []
  offset = 0
  page = min(100, limit)
  while len(rows) < limit:
    q = {**params, "limit": page, "offset": offset}
    data = get_json(url, params=q)
    chunk = data.get("mechanisms") or data.get("activities") or data.get("targets") or []
    if not chunk:
      # some endpoints return page_meta + list under resource name
      for key, val in data.items():
        if isinstance(val, list) and key not in {"page_meta"}:
          chunk = val
          break
    if not chunk:
      break
    rows.extend(chunk)
    total = (data.get("page_meta") or {}).get("total_count")
    offset += len(chunk)
    if total is not None and offset >= int(total):
      break
    if len(chunk) < page:
      break
  return rows[:limit]


def fetch_mechanisms(chembl_id: str) -> list[dict]:
  return _paginate(
    f"{CHEMBL_API}/mechanism.json",
    {"molecule_chembl_id": chembl_id},
    limit=50,
  )


def fetch_activities(chembl_id: str, *, limit: int | None = None) -> list[dict]:
  settings = get_settings()
  lim = limit or settings.chembl_activity_limit
  return _paginate(
    f"{CHEMBL_API}/activity.json",
    {
      "molecule_chembl_id": chembl_id,
      "standard_type__in": ",".join(sorted(AFFINITY_TYPES)),
      "target_organism": "Homo sapiens",
    },
    limit=lim,
  )


def fetch_target(target_chembl_id: str) -> dict | None:
  try:
    return get_json(f"{CHEMBL_API}/target/{target_chembl_id}.json")
  except Exception:  # noqa: BLE001
    return None


def _gene_from_target_payload(payload: dict | None) -> tuple[str | None, str | None, str | None]:
  """Return gene_symbol, uniprot_id, protein_name."""
  if not payload:
    return None, None, None
  pref = payload.get("pref_name")
  gene = None
  uniprot = None
  for comp in payload.get("target_components") or []:
    for xref in comp.get("target_component_xrefs") or []:
      src = (xref.get("xref_src_db") or "").upper()
      if src == "UNIPROT" and not uniprot:
        uniprot = xref.get("xref_id")
      if src in {"GENE_SYMBOL", "HGNC"} and not gene:
        gene = xref.get("xref_id")
    if not gene:
      gene = comp.get("gene_symbol") or comp.get("component_synonym")
  return gene, uniprot, pref


def _best_affinity_nm(acts: list[dict], target_chembl_id: str) -> tuple[float | None, str | None]:
  best: float | None = None
  best_type: str | None = None
  for a in acts:
    if a.get("target_chembl_id") != target_chembl_id:
      continue
    st = a.get("standard_type")
    if st not in AFFINITY_TYPES:
      continue
    val = a.get("standard_value")
    if val is None:
      continue
    nm = to_nm(float(val), a.get("standard_units"))
    if nm is None:
      continue
    if best is None or nm < best:
      best = nm
      best_type = st
  return best, best_type


def build_drug_target_rows(
  *,
  drug_id: str,
  chembl_id: str,
  primary_target_ids: set[str],
  activities: list[dict] | None = None,
  mechanisms: list[dict] | None = None,
  target_cache: dict[str, dict] | None = None,
) -> tuple[list[dict], list[dict]]:
  """Return (targets, drug_targets) normalized rows for DB upsert."""
  acts = activities if activities is not None else fetch_activities(chembl_id)
  mechs = mechanisms if mechanisms is not None else fetch_mechanisms(chembl_id)
  cache = target_cache if target_cache is not None else {}

  target_chembl_ids: set[str] = set()
  mech_action: dict[str, str] = {}
  for m in mechs:
    tid = m.get("target_chembl_id")
    if tid:
      target_chembl_ids.add(tid)
      if m.get("action_type"):
        mech_action[tid] = m["action_type"]

  for a in acts:
    tid = a.get("target_chembl_id")
    if tid:
      target_chembl_ids.add(tid)

  targets: list[dict] = []
  drug_targets: list[dict] = []
  seen_pairs: set[tuple[str, str]] = set()

  for t_chembl in sorted(target_chembl_ids):
    if t_chembl not in cache:
      cache[t_chembl] = fetch_target(t_chembl) or {}
    gene, uniprot, pref = _gene_from_target_payload(cache[t_chembl])
    if not gene:
      # skip unresolvable multi-protein complexes without a gene symbol
      continue
    target_id = target_id_from_symbol(gene)
    targets.append(
      {
        "target_id": target_id,
        "gene_symbol": gene.upper() if gene else gene,
        "uniprot_id": uniprot,
        "ensembl_id": None,
        "protein_name": pref,
        "is_admet_relevant": gene.upper() in {"CYP3A4", "CYP2D6", "CYP1A2", "CYP2C9", "CYP2C19"},
      }
    )
    affinity_nm, affinity_type = _best_affinity_nm(acts, t_chembl)
    is_off = target_id not in primary_target_ids
    key = (drug_id, target_id)
    if key in seen_pairs:
      continue
    seen_pairs.add(key)
    drug_targets.append(
      {
        "drug_id": drug_id,
        "target_id": target_id,
        "affinity_nm": affinity_nm,
        "affinity_type": affinity_type,
        "action_type": mech_action.get(t_chembl, "inhibitor"),
        "is_off_target": is_off,
        "source": "chembl",
      }
    )

  return targets, drug_targets


# Back-compat for earlier stub name
def fetch_drug_targets_stub(chembl_id: str) -> list[dict]:
  return fetch_activities(chembl_id, limit=5)
