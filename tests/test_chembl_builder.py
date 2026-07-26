"""ChEMBL offline builder tests."""

from __future__ import annotations

from ingest.chembl import build_drug_target_rows


def test_build_drug_target_rows_marks_off_target():
  mechanisms = [{"target_chembl_id": "T1", "action_type": "INHIBITOR"}]
  activities = [
    {
      "target_chembl_id": "T1",
      "standard_type": "IC50",
      "standard_value": 10,
      "standard_units": "nM",
    },
    {
      "target_chembl_id": "T2",
      "standard_type": "IC50",
      "standard_value": 500,
      "standard_units": "nM",
    },
  ]
  targets = {
    "T1": {
      "pref_name": "ABL1",
      "target_components": [
        {"gene_symbol": "ABL1", "target_component_xrefs": [{"xref_src_db": "UniProt", "xref_id": "P00519"}]}
      ],
    },
    "T2": {
      "pref_name": "EGFR",
      "target_components": [
        {"gene_symbol": "EGFR", "target_component_xrefs": [{"xref_src_db": "UniProt", "xref_id": "P00533"}]}
      ],
    },
  }
  trows, dtrows = build_drug_target_rows(
    drug_id="drug_imatinib",
    chembl_id="CHEMBL941",
    primary_target_ids={"tgt_abl1"},
    activities=activities,
    mechanisms=mechanisms,
    target_cache=targets,
  )
  by_tgt = {r["target_id"]: r for r in dtrows}
  assert by_tgt["tgt_abl1"]["is_off_target"] is False
  assert by_tgt["tgt_egfr"]["is_off_target"] is True
  assert by_tgt["tgt_abl1"]["affinity_nm"] == 10.0
  assert len(trows) == 2
