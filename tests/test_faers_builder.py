"""Unit tests for FAERS row builder (no network)."""

from __future__ import annotations

from ingest.faers import build_faers_rows, faers_filter_note


def test_faers_filter_note_mentions_kinase_slice():
  note = faers_filter_note()
  assert "kinase" in note.lower() or "seed" in note.lower()
  assert "full" in note.lower()


def test_build_faers_rows_maps_pt_and_case():
  events = [
    {
      "safetyreportid": "999",
      "serious": "1",
      "receiptdate": "20240101",
      "patient": {
        "drug": [
          {
            "medicinalproduct": "IMATINIB",
            "drugcharacterization": "1",
            "drugdosagetext": "400 mg daily",
          }
        ],
        "reaction": [{"reactionmeddrapt": "Rash"}],
      },
    }
  ]
  aes, cases, links = build_faers_rows(
    drug_id="drug_imatinib", drug_name="imatinib", events=events
  )
  assert len(aes) == 1
  assert aes[0]["pt_string"] == "Rash"
  assert cases[0]["case_id"] == "faers_999"
  assert cases[0]["serious"] is True
  assert links[0]["ae_term_id"] == aes[0]["ae_term_id"]
  assert links[0]["drug_role"] == "PS"
