"""AlphaFold structure references (fixture-backed with live lookup).

Mirrors the ingest/sec_edgar.py pattern: stable identifier mapping works
offline; the live European Bioinformatics Institute API needs no auth.
Only identifier facts are fixtured (gene -> UniProtKB accession, both
stable public identifiers). Predicted coordinates / pLDDT are NEVER
fixtured — they come only from a live API call.

Live API: https://alphafold.ebi.ac.uk/api/prediction/{uniprot_id}
Docs: https://alphafold.ebi.ac.uk/api-docs
"""

from __future__ import annotations

from typing import Any

AF_API = "https://alphafold.ebi.ac.uk/api"
AF_ENTRY_PAGE = "https://alphafold.ebi.ac.uk/entry"

# Pharmacogene symbol -> UniProtKB accession (stable public identifiers).
GENE_UNIPROT: dict[str, str] = {
    "CYP2D6": "P10635",
    "CYP2C9": "P11712",
    "CYP2C19": "P33261",
    "CYP3A4": "P08684",
    "CYP3A5": "P20815",
    "DPYD": "Q12882",
    "G6PD": "P11413",
    "HLA-B": "P01889",
    "SLCO1B1": "Q9Y6L6",
    "TPMT": "P51580",
    "UGT1A1": "P22309",
    "VKORC1": "Q9BQB6",
}


def prediction_api_url(uniprot_id: str) -> str:
    """Live prediction-summary endpoint for a UniProt accession."""
    return f"{AF_API}/prediction/{uniprot_id.strip().upper()}"


def entry_page_url(uniprot_id: str) -> str:
    """Human-readable AlphaFold entry page for a UniProt accession."""
    return f"{AF_ENTRY_PAGE}/{uniprot_id.strip().upper()}"


def uniprot_for_gene(gene_symbol: str) -> str | None:
    """Offline UniProtKB fixture (None when unknown — never guessed)."""
    return GENE_UNIPROT.get(gene_symbol.strip().upper())


def fetch_live_prediction(uniprot_id: str) -> list[dict[str, Any]] | None:
    """Live AlphaFold prediction summary. None on any failure (offline-safe)."""
    from ingest.http_util import get_json

    try:
        payload = get_json(prediction_api_url(uniprot_id))
    except Exception:  # noqa: BLE001 -- network or schema failure means offline fallback
        return None
    return payload if isinstance(payload, list) else None


def protein_entry(gene_symbol: str, *, live: bool = False) -> dict[str, Any]:
    """One pharmacogene -> {uniprot, af_url, source} dict for omic use."""
    gene = gene_symbol.strip().upper()
    uniprot = uniprot_for_gene(gene)
    if uniprot is None:
        return {"gene": gene, "uniprot": None, "af_url": None, "source": "unmapped"}
    entry: dict[str, Any] = {
        "gene": gene,
        "uniprot": uniprot,
        "af_url": entry_page_url(uniprot),
        "source": "fixture",
    }
    if live:
        summary = fetch_live_prediction(uniprot)
        if summary:
            entry["source"] = "live_alphafold"
            entry["prediction_summary"] = summary
    return entry


def gene_coverage() -> dict[str, Any]:
    """Coverage summary over the fixtured pharmacogene set."""
    return {
        "genes": len(GENE_UNIPROT),
        "mapped": sum(1 for g in GENE_UNIPROT if uniprot_for_gene(g) is not None),
    }
