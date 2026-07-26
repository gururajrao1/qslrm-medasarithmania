"""Resolve empty-sponsor flagship drugs via openFDA + RxNorm (public APIs)."""

from __future__ import annotations

import json
from pathlib import Path

from ingest.http_util import get_json

PREFERRED = {
  "Amgen": [("sotorasib", "Lumakras"), ("denosumab", "Prolia"), ("evolocumab", "Repatha")],
  "Biogen": [("natalizumab", "Tysabri"), ("dimethyl fumarate", "Tecfidera")],
  "Boehringer Ingelheim": [("nintedanib", "Ofev"), ("empagliflozin", "Jardiance")],
  "Eli Lilly": [("baricitinib", "Olumiant"), ("abemaciclib", "Verzenio"), ("dulaglutide", "Trulicity")],
  "Gilead Sciences": [("remdesivir", "Veklury"), ("sofosbuvir", "Sovaldi")],
  "GSK (GlaxoSmithKline)": [("trametinib", "Mekinist"), ("mepolizumab", "Nucala")],
  "Johnson & Johnson (Janssen)": [("daratumumab", "Darzalex"), ("ustekinumab", "Stelara"), ("rivaroxaban", "Xarelto")],
  "Regeneron": [("cemiplimab", "Libtayo"), ("alirocumab", "Praluent")],
  "Takeda": [("vedolizumab", "Entyvio"), ("ixazomib", "Ninlaro")],
  "Vertex Pharmaceuticals": [("ivacaftor", "Kalydeco"), ("elexacaftor", "Trikafta")],
}

BIOLOGIC_NAMES = {
  "denosumab",
  "evolocumab",
  "natalizumab",
  "dulaglutide",
  "mepolizumab",
  "daratumumab",
  "ustekinumab",
  "cemiplimab",
  "alirocumab",
  "vedolizumab",
}

# Curated fallbacks when API is rate-limited / sparse (still public FDA IDs)
FALLBACK = {
  "Amgen": {
    "preferred_name": "sotorasib",
    "brand_name": "Lumakras",
    "molecule_type": "small_molecule",
    "drug_class": "kinase_inhibitor",
    "therapeutic_class": "solid_tumor_oncology",
    "nda_bla": "NDA214665",
    "atc_code": "L01XX73",
    "rxnorm_cui": "2556674",
    "chembl_id": "CHEMBL4559787",
    "cyp_substrates": "CYP3A4",
    "notes": "KRAS G12C inhibitor (Amgen); openFDA/Orange Book",
    "primary_aes": ["Diarrhoea", "Hepatotoxicity", "Nausea"],
    "target": {"gene": "KRAS", "uniprot": "P01116", "ensembl": "ENSG00000133703", "pdb": "4OBE", "protein": "GTPase KRas"},
  },
  "Biogen": {
    "preferred_name": "natalizumab",
    "brand_name": "Tysabri",
    "molecule_type": "biologic",
    "drug_class": "monoclonal_antibody",
    "therapeutic_class": "neurology",
    "nda_bla": "BLA125104",
    "atc_code": "L04AA23",
    "rxnorm_cui": "354770",
    "chembl_id": "CHEMBL1201581",
    "cyp_substrates": None,
    "notes": "Anti-α4 integrin mAb (Biogen); PML BBW",
    "primary_aes": ["Progressive multifocal leukoencephalopathy", "Hypersensitivity", "Hepatotoxicity"],
    "target": {"gene": "ITGA4", "uniprot": "P13612", "ensembl": "ENSG00000115232", "pdb": "1GCQ", "protein": "Integrin alpha-4"},
  },
  "Boehringer Ingelheim": {
    "preferred_name": "nintedanib",
    "brand_name": "Ofev",
    "molecule_type": "small_molecule",
    "drug_class": "kinase_inhibitor",
    "therapeutic_class": "pulmonary",
    "nda_bla": "NDA205832",
    "atc_code": "L01EX09",
    "rxnorm_cui": "1592737",
    "chembl_id": "CHEMBL502835",
    "cyp_substrates": "CYP3A4",
    "notes": "VEGFR/FGFR/PDGFR TKI (Boehringer); IPF",
    "primary_aes": ["Diarrhoea", "Nausea", "Hepatotoxicity"],
    "target": {"gene": "KDR", "uniprot": "P35968", "ensembl": "ENSG00000128052", "pdb": "3VHE", "protein": "VEGFR2"},
  },
  "Eli Lilly": {
    "preferred_name": "baricitinib",
    "brand_name": "Olumiant",
    "molecule_type": "small_molecule",
    "drug_class": "kinase_inhibitor",
    "therapeutic_class": "immunology",
    "nda_bla": "NDA207924",
    "atc_code": "L04AA37",
    "rxnorm_cui": "1927851",
    "chembl_id": "CHEMBL2105759",
    "cyp_substrates": "CYP3A4",
    "notes": "JAK1/2 inhibitor (Eli Lilly); infection / thrombosis BBW",
    "primary_aes": ["Infection", "Thrombosis", "Hepatotoxicity"],
    "target": {"gene": "JAK1", "uniprot": "P23458", "ensembl": "ENSG00000162434", "pdb": "6N7A", "protein": "JAK1"},
  },
  "Gilead Sciences": {
    "preferred_name": "remdesivir",
    "brand_name": "Veklury",
    "molecule_type": "small_molecule",
    "drug_class": "antiviral",
    "therapeutic_class": "infectious_disease",
    "nda_bla": "NDA214787",
    "atc_code": "J05AB16",
    "rxnorm_cui": "2284762",
    "chembl_id": "CHEMBL4065616",
    "cyp_substrates": "CYP3A4",
    "notes": "SARS-CoV-2 RdRp inhibitor (Gilead)",
    "primary_aes": ["Hepatotoxicity", "Nausea", "Infusion related reaction"],
    "target": {"gene": "nsp12", "uniprot": "P0DTD1", "ensembl": None, "pdb": "7BV2", "protein": "SARS-CoV-2 RNA-dependent RNA polymerase"},
  },
  "GSK (GlaxoSmithKline)": {
    "preferred_name": "trametinib",
    "brand_name": "Mekinist",
    "molecule_type": "small_molecule",
    "drug_class": "kinase_inhibitor",
    "therapeutic_class": "solid_tumor_oncology",
    "nda_bla": "NDA204114",
    "atc_code": "L01EE01",
    "rxnorm_cui": "1422430",
    "chembl_id": "CHEMBL2103875",
    "cyp_substrates": "CYP3A4",
    "notes": "MEK1/2 inhibitor (GSK / Novartis co-promote historically)",
    "primary_aes": ["Rash", "Diarrhoea", "Cardiomyopathy"],
    "target": {"gene": "MAP2K1", "uniprot": "Q02750", "ensembl": "ENSG00000169032", "pdb": "3EQC", "protein": "Dual specificity mitogen-activated protein kinase kinase 1"},
  },
  "Johnson & Johnson (Janssen)": {
    "preferred_name": "daratumumab",
    "brand_name": "Darzalex",
    "molecule_type": "biologic",
    "drug_class": "monoclonal_antibody",
    "therapeutic_class": "hematologic_oncology",
    "nda_bla": "BLA761036",
    "atc_code": "L01FC01",
    "rxnorm_cui": "1723735",
    "chembl_id": "CHEMBL1743007",
    "cyp_substrates": None,
    "notes": "Anti-CD38 mAb (Janssen/J&J)",
    "primary_aes": ["Infusion related reaction", "Infection", "Neutropenia"],
    "target": {"gene": "CD38", "uniprot": "P28907", "ensembl": "ENSG00000004468", "pdb": "1YH3", "protein": "ADP-ribosyl cyclase/cyclic ADP-ribose hydrolase 1"},
  },
  "Regeneron": {
    "preferred_name": "cemiplimab",
    "brand_name": "Libtayo",
    "molecule_type": "biologic",
    "drug_class": "monoclonal_antibody",
    "therapeutic_class": "solid_tumor_oncology",
    "nda_bla": "BLA761097",
    "atc_code": "L01FF06",
    "rxnorm_cui": "2058844",
    "chembl_id": "CHEMBL4297867",
    "cyp_substrates": None,
    "notes": "Anti-PD-1 mAb (Regeneron/Sanofi)",
    "primary_aes": ["Immune-mediated colitis", "Rash", "Hepatotoxicity"],
    "target": {"gene": "PDCD1", "uniprot": "Q15116", "ensembl": "ENSG00000188389", "pdb": "5GGS", "protein": "Programmed cell death protein 1"},
  },
  "Takeda": {
    "preferred_name": "vedolizumab",
    "brand_name": "Entyvio",
    "molecule_type": "biologic",
    "drug_class": "monoclonal_antibody",
    "therapeutic_class": "immunology",
    "nda_bla": "BLA125476",
    "atc_code": "L04AA33",
    "rxnorm_cui": "1534763",
    "chembl_id": "CHEMBL1743034",
    "cyp_substrates": None,
    "notes": "Anti-α4β7 integrin mAb (Takeda)",
    "primary_aes": ["Infection", "Nasopharyngitis", "Hepatotoxicity"],
    "target": {"gene": "ITGB7", "uniprot": "P26010", "ensembl": "ENSG00000139626", "pdb": "3V4P", "protein": "Integrin beta-7"},
  },
  "Vertex Pharmaceuticals": {
    "preferred_name": "ivacaftor",
    "brand_name": "Kalydeco",
    "molecule_type": "small_molecule",
    "drug_class": "cftr_modulator",
    "therapeutic_class": "pulmonary",
    "nda_bla": "NDA203188",
    "atc_code": "R07AX02",
    "rxnorm_cui": "1242987",
    "chembl_id": "CHEMBL2010601",
    "cyp_substrates": "CYP3A4",
    "notes": "CFTR potentiator (Vertex)",
    "primary_aes": ["Hepatotoxicity", "Headache", "Rash"],
    "target": {"gene": "CFTR", "uniprot": "P13569", "ensembl": "ENSG00000001626", "pdb": "5UAK", "protein": "Cystic fibrosis transmembrane conductance regulator"},
  },
}


def enrich_from_openfda(row: dict) -> dict:
  name = row["preferred_name"]
  brand = row["brand_name"]
  for field, term in (("openfda.generic_name", name), ("openfda.brand_name", brand)):
    try:
      data = get_json(
        "https://api.fda.gov/drug/label.json",
        params={"search": f'{field}:"{term}"', "limit": 1},
      )
    except Exception as exc:  # noqa: BLE001
      print(f"  openFDA miss {term}: {exc}")
      continue
    results = data.get("results") or []
    if not results:
      continue
    of = results[0].get("openfda") or {}
    if of.get("rxcui") and not row.get("rxnorm_cui"):
      row["rxnorm_cui"] = str(of["rxcui"][0])
    if of.get("application_number"):
      row["nda_bla"] = of["application_number"][0]
    if of.get("brand_name"):
      row["brand_name"] = of["brand_name"][0]
    if of.get("manufacturer_name"):
      row["openfda_manufacturer"] = of["manufacturer_name"][0]
    print(f"  openFDA hit {name}: {row.get('brand_name')} {row.get('nda_bla')} rx={row.get('rxnorm_cui')}")
    break
  return row


def enrich_rxnorm(row: dict) -> dict:
  if row.get("rxnorm_cui"):
    return row
  try:
    data = get_json(
      "https://rxnav.nlm.nih.gov/REST/rxcui.json",
      params={"name": row["preferred_name"]},
    )
    rxcui = ((data.get("idGroup") or {}).get("rxnormId") or [None])[0]
    if rxcui:
      row["rxnorm_cui"] = str(rxcui)
      print(f"  RxNorm hit {row['preferred_name']}: {rxcui}")
  except Exception as exc:  # noqa: BLE001
    print(f"  RxNorm miss {row['preferred_name']}: {exc}")
  return row


def main() -> None:
  out: dict[str, dict] = {}
  for sponsor, base in FALLBACK.items():
    row = dict(base)
    row["sponsor_company"] = sponsor
    if row["preferred_name"] in BIOLOGIC_NAMES:
      row["molecule_type"] = "biologic"
    print(f"Resolving {sponsor} / {row['preferred_name']}…")
    enrich_from_openfda(row)
    enrich_rxnorm(row)
    out[sponsor] = row
  path = Path("data/processed/sponsor_fill_openfda.json")
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(json.dumps(out, indent=2), encoding="utf-8")
  print(f"Wrote {path} ({len(out)} sponsors)")


if __name__ == "__main__":
  main()
