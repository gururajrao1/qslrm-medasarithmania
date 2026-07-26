"""Open Targets GraphQL — pathway annotations for Ensembl gene IDs."""

from __future__ import annotations

from typing import Any

from ingest.http_util import post_json
from ingest.normalize import pathway_id_from_source

OT_GRAPHQL = "https://api.platform.opentargets.org/api/v4/graphql"

_PATHWAY_QUERY = """
query TargetPathways($ensemblId: String!) {
  target(ensemblId: $ensemblId) {
    id
    approvedSymbol
    pathways {
      pathwayId
      pathway
      topLevelTerm
    }
  }
}
"""

_TOX_HINTS = {
  "hepat": "hepatotox",
  "liver": "hepatotox",
  "cytochrome": "hepatotox",
  "xenobiotic": "hepatotox",
  "skin": "dermal",
  "keratin": "dermal",
  "egfr": "dermal",
  "angiogen": "vascular",
  "vegf": "vascular",
  "cardiac": "cardio",
  "heart": "cardio",
}


def _tox_tag(name: str | None) -> str | None:
  text = (name or "").lower()
  for needle, tag in _TOX_HINTS.items():
    if needle in text:
      return tag
  return None


def fetch_target_pathways(ensembl_id: str) -> list[dict]:
  """Live OT pathways for one Ensembl gene."""
  data = post_json(OT_GRAPHQL, {"query": _PATHWAY_QUERY, "variables": {"ensemblId": ensembl_id}})
  target = ((data or {}).get("data") or {}).get("target") or {}
  return list(target.get("pathways") or [])


def fetch_target_pathways_stub(ensembl_id: str) -> list[dict]:
  return fetch_target_pathways(ensembl_id)


def build_pathway_rows(
  *,
  target_id: str,
  ensembl_id: str,
  pathways: list[dict] | None = None,
  max_pathways: int = 25,
) -> tuple[list[dict], list[dict]]:
  raw = pathways if pathways is not None else fetch_target_pathways(ensembl_id)
  pathway_rows: list[dict] = []
  link_rows: list[dict] = []
  for p in raw[:max_pathways]:
    pid_src = p.get("pathwayId") or ""
    name = p.get("pathway") or p.get("topLevelTerm") or pid_src or "unknown"
    pathway_id = pathway_id_from_source(str(pid_src), str(name))
    pathway_rows.append(
      {
        "pathway_id": pathway_id,
        "name": str(name)[:256],
        "source": "opentargets",
        "tox_tag": _tox_tag(str(name)),
      }
    )
    link_rows.append({"pathway_id": pathway_id, "target_id": target_id})
  return pathway_rows, link_rows


def parse_pathways_payload(data: dict[str, Any]) -> list[dict]:
  target = ((data or {}).get("data") or {}).get("target") or {}
  return list(target.get("pathways") or [])
