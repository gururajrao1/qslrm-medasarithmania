"""Data sources that are wired (live client and/or offline fixtures)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ingest.http_util import get_json, post_json


@dataclass(frozen=True)
class DataSource:
  key: str
  name: str
  domain: str
  base_url: str
  auth: str
  notes: str


SOURCES: list[DataSource] = [
  DataSource("openfda_faers", "openFDA FAERS", "pharmacovigilance", "https://api.fda.gov/drug/event.json", "optional key", "US spontaneous reports"),
  DataSource("eudravigilance", "EudraVigilance (fixture)", "pharmacovigilance", "https://www.adrreports.eu", "fixtures MVP", "EU spontaneous reports · region=EU"),
  DataSource("openvigil", "OpenVigilFDA", "pharmacovigilance", "http://openvigil.pharmacology.uni-kiel.de", "reference", "FAERS analytics companion"),
  DataSource("orange_book", "FDA Orange Book / Purple Book", "regulatory", "https://www.fda.gov/drugs/drug-approvals-and-databases/orange-book-data-files", "fixtures + openFDA", "NDA/BLA · applicant · molecule type · sponsor portfolio fill"),
  DataSource("openfda_label", "openFDA Drug Labeling (SPL)", "literature", "https://api.fda.gov/drug/label.json", "optional key", "Adverse reactions / boxed warning sections from SPL JSON"),
  DataSource("chembl", "ChEMBL", "multiomic", "https://www.ebi.ac.uk/chembl/api/data", "none", "Target affinities → S_off"),
  DataSource("bindingdb", "BindingDB", "multiomic", "https://www.bindingdb.org", "fixtures MVP", "Ki/IC50 affinities complementing ChEMBL"),
  DataSource("tox21", "Tox21 / NCATS", "multiomic", "https://tripod.nih.gov/tox21", "fixtures MVP", "HTS nuclear receptor / stress pathway assays"),
  DataSource("depmap", "DepMap", "multiomic", "https://depmap.org", "fixtures MVP", "CRISPR gene dependency chronos scores"),
  DataSource("opentargets", "Open Targets", "multiomic", "https://api.platform.opentargets.org/api/v4/graphql", "none", "Tox pathways + gene–disease–drug evidence"),
  DataSource("opentargets_pv", "Open Targets Pharmacovigilance", "literature", "https://api.platform.opentargets.org/api/v4/graphql", "none", "FAERS LRT significant drug–ADR (health-professional filtered)"),
  DataSource("clinvar", "ClinVar", "multiomic", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils", "optional", "Variants → S_gen"),
  DataSource("lincs", "LINCS L1000", "multiomic", "https://api.clue.io", "fixtures MVP", "Transcript z-scores → S_trans"),
  DataSource("ctgov", "ClinicalTrials.gov v2", "clinical_trials", "https://clinicaltrials.gov/api/v2/studies", "none", "Arms, dose, AE onset · sponsor filterable"),
  DataSource("rxnorm", "RxNorm (NLM)", "ontology", "https://rxnav.nlm.nih.gov/REST", "none", "Drug / concomitant IDs · sponsor portfolio RxCUI resolve"),
  DataSource("ictrp_ctri", "WHO ICTRP / CTRI India", "clinical_trials", "https://trialsearch.who.int", "fixtures MVP", "Global registry arms · CTRI India → Global region PV"),
  DataSource("synthea", "Synthea Synthetic EHR", "rwe", "https://synthetichealth.github.io/synthea", "fixtures MVP", "Synthetic exposure / t_onset curves (no PHI)"),
  DataSource("pharmgkb", "PharmGKB / CYP", "multiomic", "https://api.pharmgkb.org/v1", "fixtures MVP", "Metabolizer + DDI CYP + CPIC dosing"),
  DataSource("pubmed", "PubMed / MEDLINE", "literature", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils", "optional NCBI key", "Peer-reviewed drug–ADR abstracts (Entrez cascade)"),
  DataSource("europepmc", "Europe PMC", "literature", "https://www.ebi.ac.uk/europepmc/webservices/rest", "none", "Open full-text / preprints for evidence extraction"),
  DataSource("semantic_scholar", "Semantic Scholar", "literature", "https://api.semanticscholar.org", "optional key", "Citation influence for toxicity papers"),
  DataSource("sider", "SIDER", "literature", "http://sideeffects.embl.de", "fixtures MVP", "Package-insert side-effect frequency × MedDRA PT"),
  DataSource("onsides", "OnSIDES", "literature", "https://github.com/tatonetti-lab/onsides", "fixtures MVP", "PubMedBERT ADEs from DailyMed/EMA/EMC/KEGG labels"),
  DataSource("biodex", "BioDEX", "literature", "https://github.com/KarelDO/BioDEX", "benchmark / fixtures", "19k full-text + 65k abstracts ADE extraction benchmark (HF: BioDEX)"),
  DataSource("kidsides", "Kidsides", "literature", "https://github.com/ngiangre/kidsides", "fixtures MVP", "Pediatric age-stage FAERS ADE risk enrichment"),
  DataSource("drug_repurposing_hub", "Broad Drug Repurposing Hub", "multiomic", "https://www.broadinstitute.org/drug-repurposing-hub", "download / fixtures", "~6k clinical compounds · targets · phase metadata"),
]


def sources_manifest() -> list[dict[str, str]]:
  return [
    {
      "key": s.key,
      "name": s.name,
      "domain": s.domain,
      "base_url": s.base_url,
      "auth": s.auth,
      "notes": s.notes,
    }
    for s in SOURCES
  ]


def fetch_faers_drug(drug_name: str, *, limit: int = 25) -> dict[str, Any]:
  return get_json(
    "https://api.fda.gov/drug/event.json",
    params={"search": f'patient.drug.medicinalproduct:"{drug_name}"', "limit": limit},
  )


def fetch_openfda_label(drug_name: str, *, limit: int = 3) -> dict[str, Any]:
  """SPL sections including adverse_reactions / boxed_warning."""
  return get_json(
    "https://api.fda.gov/drug/label.json",
    params={"search": f'openfda.generic_name:"{drug_name}"', "limit": limit},
  )


def fetch_ctgov_studies(query: str, *, page_size: int = 5, sponsor: str | None = None) -> dict[str, Any]:
  params: dict[str, Any] = {"query.term": query, "pageSize": page_size, "format": "json"}
  if sponsor:
    params["query.spons"] = sponsor
  return get_json("https://clinicaltrials.gov/api/v2/studies", params=params)


def fetch_ctgov_by_sponsor(sponsor: str, *, page_size: int = 10) -> dict[str, Any]:
  """BD helper: list studies for a lead sponsor (e.g. Pfizer, Novartis)."""
  return get_json(
    "https://clinicaltrials.gov/api/v2/studies",
    params={"query.spons": sponsor, "pageSize": page_size, "format": "json"},
  )


def fetch_pubmed_ids(query: str, *, retmax: int = 5) -> dict[str, Any]:
  return get_json(
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
    params={"db": "pubmed", "term": query, "retmode": "json", "retmax": retmax},
  )


def fetch_europepmc(query: str, *, page_size: int = 5) -> dict[str, Any]:
  return get_json(
    "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
    params={"query": query, "format": "json", "pageSize": page_size},
  )


def fetch_semantic_scholar(query: str, *, limit: int = 5) -> dict[str, Any]:
  return get_json(
    "https://api.semanticscholar.org/graph/v1/paper/search",
    params={"query": query, "limit": limit, "fields": "title,year,citationCount,abstract,externalIds"},
  )


def literature_search_cascade(drug: str, ae: str, *, retmax: int = 5) -> dict[str, Any]:
  """Multi-tier evidence search: PubMed → Europe PMC → Semantic Scholar."""
  q = f"{drug} {ae} adverse"
  tiers: dict[str, Any] = {"query": q, "tiers": {}}
  try:
    tiers["tiers"]["pubmed"] = fetch_pubmed_ids(q, retmax=retmax)
  except Exception as exc:  # noqa: BLE001 — cascade must degrade gracefully
    tiers["tiers"]["pubmed"] = {"error": str(exc)}
  try:
    tiers["tiers"]["europepmc"] = fetch_europepmc(q, page_size=retmax)
  except Exception as exc:  # noqa: BLE001
    tiers["tiers"]["europepmc"] = {"error": str(exc)}
  try:
    tiers["tiers"]["semantic_scholar"] = fetch_semantic_scholar(q, limit=retmax)
  except Exception as exc:  # noqa: BLE001
    tiers["tiers"]["semantic_scholar"] = {"error": str(exc)}
  return tiers


def fetch_chembl_molecule(chembl_id: str) -> dict[str, Any]:
  return get_json(f"https://www.ebi.ac.uk/chembl/api/data/molecule/{chembl_id}.json")


def fetch_opentargets_target(ensembl_id: str) -> dict[str, Any]:
  query = """
  query target($ensemblId: String!) {
    target(ensemblId: $ensemblId) {
      id
      approvedSymbol
      pathways { pathway pathwayId }
    }
  }
  """
  return post_json(
    "https://api.platform.opentargets.org/api/v4/graphql",
    {"query": query, "variables": {"ensemblId": ensembl_id}},
  )


def fetch_opentargets_adverse_events(chembl_id: str, *, size: int = 25) -> dict[str, Any]:
  """Significant FAERS LRT adverse events for a ChEMBL drug."""
  query = """
  query drugPv($chemblId: String!, $size: Int!) {
    drug(chemblId: $chemblId) {
      id
      name
      blackBoxWarning
      adverseEvents(page: { index: 0, size: $size }) {
        count
        criticalValue
        rows { name count meddraCode logLR }
      }
    }
  }
  """
  return post_json(
    "https://api.platform.opentargets.org/api/v4/graphql",
    {"query": query, "variables": {"chemblId": chembl_id, "size": size}},
  )
