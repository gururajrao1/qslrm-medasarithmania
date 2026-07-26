"""FAERS narrative coercion — openFDA sometimes returns dict narratives."""

from __future__ import annotations

from ingest.faers import _as_text, build_faers_rows


def test_as_text_coerces_openfda_narrative_dict():
  raw = {"narrativeincludeclinical": "CASE EVENT DATE: 20120621"}
  assert _as_text(raw) == "CASE EVENT DATE: 20120621"
  assert isinstance(_as_text(raw, fallback="x"), str)


def test_build_faers_rows_dict_narrative_ok():
  events = [
    {
      "safetyreportid": "10026717",
      "serious": "1",
      "receiptdate": "20140530",
      "occurcountry": "GB",
      "narrative": {"narrativeincludeclinical": "CASE EVENT DATE: 20120621"},
      "patient": {
        "patientsex": "2",
        "patientonsetage": "70",
        "drug": [
          {
            "medicinalproduct": "IMATINIB",
            "drugcharacterization": "1",
            "drugdosagetext": "400 mg",
          }
        ],
        "reaction": [{"reactionmeddrapt": "Nausea", "reactionoutcome": "3"}],
      },
    }
  ]
  _aes, cases, links = build_faers_rows(
    drug_id="drug_imatinib",
    drug_name="imatinib",
    events=events,
  )
  assert len(cases) == 1
  assert cases[0]["narrative"] == "CASE EVENT DATE: 20120621"
  assert isinstance(cases[0]["narrative"], str)
  assert links[0]["pt_string"] == "Nausea"
