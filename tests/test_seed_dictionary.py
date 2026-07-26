"""Seed dictionary sanity — Phase 0 lockdown checks."""

from __future__ import annotations

from qslrm_erd.seeds import kinase_mvp as seed


def test_mvp_class_is_kinase_only():
  classes = {d["drug_class"] for d in seed.drugs}
  assert "kinase_inhibitor" in classes
  # Biologic ADR seeds (mRNA vaccines / mAbs) are allowed alongside kinase MVP
  assert classes <= {
    "kinase_inhibitor",
    "mrna_vaccine",
    "monoclonal_antibody",
    "antiviral",
    "cftr_modulator",
  }
  assert all(d["is_mvp_seed"] for d in seed.drugs)
  assert all(d.get("sponsor_company") and d.get("molecule_type") for d in seed.drugs)
  assert len(seed.drugs) >= 17
  assert any(d["sponsor_company"] == "BioNTech" for d in seed.drugs)
  assert any(d["molecule_type"] == "biologic" for d in seed.drugs)


def test_sponsor_portfolio_covers_empty_directory_slots():
  from qslrm_erd.seeds import sponsor_portfolio as port
  from qslrm_erd.seeds.kinase_mvp import SPONSOR_DIRECTORY

  have = {d["sponsor_company"] for d in [*seed.drugs, *port.drugs]}
  missing = [s for s in SPONSOR_DIRECTORY if s not in have]
  assert missing == [], f"Sponsors still without drugs: {missing}"
  assert len(port.drugs) == 10


def test_crosswalks_cover_rxnorm_chembl():
  drug_x = [c for c in seed.crosswalks if c["entity_type"] == "drug"]
  assert len(drug_x) == len(seed.drugs)
  assert all(c["from_system"] == "rxnorm" and c["to_system"] == "chembl" for c in drug_x)


def test_ground_truth_bbw_present():
  types = {g["label_type"] for g in seed.ground_truth}
  assert "black_box" in types
  drugs = {g["drug_id"] for g in seed.ground_truth}
  assert "drug_lapatinib" in drugs
  assert "drug_pazopanib" in drugs


def test_ae_terms_are_openfda_pt_strings():
  assert all(a["source"] == "openfda_pt" for a in seed.ae_terms)
  assert any(a["pt_string"] == "Hepatotoxicity" for a in seed.ae_terms)
