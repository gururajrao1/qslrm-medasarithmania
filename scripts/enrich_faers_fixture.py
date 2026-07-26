"""Enrich FAERS fixture demographics/narratives without rewriting every row by hand."""

from __future__ import annotations

import json
from pathlib import Path


def enrich_faers_fixture(path: Path) -> None:
  data = json.loads(path.read_text(encoding="utf-8"))
  i = 0
  for drug, events in data.items():
    for ev in events:
      i += 1
      patient = ev.setdefault("patient", {})
      if "patientsex" not in patient:
        patient["patientsex"] = "2" if i % 2 == 0 else "1"
      if "patientonsetage" not in patient:
        patient["patientonsetage"] = str(70 if i % 3 == 0 else 52)
      ev.setdefault("occurcountry", "US" if i % 4 else "JP")
      ev.setdefault("source_period", "2024q1" if i % 2 else "2023q4")
      rxns = ", ".join(
        r.get("reactionmeddrapt", "adverse event") for r in (patient.get("reaction") or [])
      )
      dose = ""
      if patient.get("drug"):
        dose = patient["drug"][0].get("drugdosagetext") or ""
      ev.setdefault(
        "narrative",
        f"On {dose or 'treatment'} with {drug}, patient developed {rxns}. "
        f"{'Off-label use noted. ' if i % 5 == 0 else ''}"
        f"Symptoms began after {1 + (i % 4)} weeks.",
      )
  path.write_text(json.dumps(data, indent=2), encoding="utf-8")


if __name__ == "__main__":
  enrich_faers_fixture(Path(__file__).resolve().parents[1] / "tests/fixtures/phase1/faers.json")
