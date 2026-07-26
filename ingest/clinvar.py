"""ClinVar + gene-toxicity variant ingest (NCBI E-utilities)."""

from __future__ import annotations

from typing import Any

from ingest.http_util import get_json
from ingest.normalize import variant_id_from_rsid

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# MVP gene panel: ADME + key kinase targets with toxicity relevance
DEFAULT_GENES = [
  "CYP2D6",
  "CYP3A4",
  "CYP1A2",
  "CYP2C9",
  "CYP2C19",
  "EGFR",
  "ABL1",
  "KDR",
  "KIT",
]

# Map gene → related openFDA PT for S_gen demos
GENE_RELATED_PT = {
  "CYP2D6": "Drug-induced liver injury",
  "CYP3A4": "Drug-induced liver injury",
  "CYP1A2": "Drug-induced liver injury",
  "CYP2C9": "Drug-induced liver injury",
  "CYP2C19": "Drug-induced liver injury",
  "EGFR": "Interstitial lung disease",
  "ABL1": "Rash",
  "KDR": "Hypertension",
  "KIT": "Rash",
}


def fetch_clinvar_ids_for_gene(gene_symbol: str, *, retmax: int = 15) -> list[str]:
  term = (
    f"{gene_symbol}[gene] AND "
    "(pathogenic[clinical_significance] OR likely_pathogenic[clinical_significance])"
  )
  data = get_json(
    f"{EUTILS}/esearch.fcgi",
    params={"db": "clinvar", "term": term, "retmax": retmax, "retmode": "json"},
  )
  idlist = ((data or {}).get("esearchresult") or {}).get("idlist") or []
  return [str(x) for x in idlist]


def fetch_clinvar_summaries(ids: list[str]) -> dict[str, Any]:
  if not ids:
    return {}
  data = get_json(
    f"{EUTILS}/esummary.fcgi",
    params={"db": "clinvar", "id": ",".join(ids), "retmode": "json"},
  )
  return ((data or {}).get("result") or {})


def _extract_rsid(summary: dict) -> str | None:
  for key in ("variation_set", "variation_set_list"):
    vs = summary.get(key)
    if isinstance(vs, list):
      for item in vs:
        if not isinstance(item, dict):
          continue
        for xref in item.get("variation_xrefs") or item.get("aliases") or []:
          if isinstance(xref, dict):
            db = (xref.get("db_source") or xref.get("db") or "").lower()
            val = xref.get("db_id") or xref.get("id")
            if "dbSNP".lower() in db or db == "dbsnp":
              return str(val)
          elif isinstance(xref, str) and xref.lower().startswith("rs"):
            return xref
  title = summary.get("title") or ""
  if "rs" in title.lower():
    import re

    m = re.search(r"rs\d+", title, flags=re.I)
    if m:
      return m.group(0)
  return None


def build_variant_rows_for_gene(
  gene_symbol: str,
  *,
  ids: list[str] | None = None,
  summaries: dict[str, Any] | None = None,
  retmax: int = 10,
) -> list[dict]:
  id_list = ids if ids is not None else fetch_clinvar_ids_for_gene(gene_symbol, retmax=retmax)
  summ = summaries if summaries is not None else fetch_clinvar_summaries(id_list)
  rows: list[dict] = []
  related_pt = GENE_RELATED_PT.get(gene_symbol.upper())
  for cid in id_list:
    s = summ.get(cid) or {}
    if not s:
      continue
    rsid = _extract_rsid(s)
    consequence = s.get("clinical_significance") or s.get("germline_classification", {}).get(
      "description"
    )
    if isinstance(consequence, dict):
      consequence = consequence.get("description")
    rows.append(
      {
        "variant_id": variant_id_from_rsid(rsid, gene_symbol, cid),
        "rsid": rsid,
        "gene_symbol": gene_symbol.upper(),
        "clinvar_id": cid,
        "consequence": str(consequence)[:128] if consequence else None,
        "allele_freq": None,
        "effect_size": 0.7 if "pathogenic" in str(consequence).lower() else 0.4,
        "related_pt": related_pt,
        "notes": (s.get("title") or "")[:500] or None,
      }
    )
  return rows


def fetch_gene_variants_stub(gene_symbol: str) -> list[dict]:
  return build_variant_rows_for_gene(gene_symbol, retmax=5)
