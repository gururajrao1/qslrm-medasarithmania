"""Generate FAERS / Orange Book / EV fixtures for sponsor portfolio fill drugs."""

from __future__ import annotations

import json
import random
from pathlib import Path

from qslrm_erd.seeds import sponsor_portfolio as port

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "phase1"
COUNTRIES = ["US", "DE", "IN", "JP", "GB", "FR", "CA", "BR", "AU", "ES"]
SEXES = ["1", "2"]
AGES = ["28", "41", "55", "63", "71"]
SERIOUS_AES = {
  "Progressive multifocal leukoencephalopathy",
  "Hepatotoxicity",
  "Thrombosis",
  "Cardiomyopathy",
  "Infusion related reaction",
  "Immune-mediated colitis",
}


def build_faers_for(name: str, dose: str, primary: list[str], start_id: int) -> tuple[list[dict], int]:
  rng = random.Random(hash(name) & 0xFFFFFFFF)
  events = []
  case_n = start_id
  for ae in primary:
    for j in range(20):
      case_n += 1
      serious = "1" if ae in SERIOUS_AES or j % 3 == 0 else "2"
      period = "2024q1" if j % 2 == 0 else "2023q4"
      country = COUNTRIES[(case_n + j) % len(COUNTRIES)]
      events.append(
        {
          "safetyreportid": str(case_n),
          "serious": serious,
          "receiptdate": (
            f"20240{(j % 9) + 1:02d}{(j % 27) + 1:02d}"
            if period == "2024q1"
            else f"2023{(10 + j % 3):02d}{(j % 27) + 1:02d}"
          ),
          "occurcountry": country,
          "source_period": period,
          "narrative": f"Patient on {dose} {name} developed {ae} after {1 + j % 6} weeks. Sponsor portfolio FAERS quarterly fixture.",
          "patient": {
            "patientsex": SEXES[(case_n + j) % 2],
            "patientonsetage": AGES[(case_n + j) % len(AGES)],
            "drug": [
              {
                "medicinalproduct": name.upper(),
                "drugcharacterization": "1",
                "drugdosagetext": dose,
              }
            ],
            "reaction": [{"reactionmeddrapt": ae, "reactionoutcome": "1" if serious == "1" else "2"}],
          },
        }
      )
  for ae in ["Nausea", "Rash"]:
    if ae in primary:
      continue
    for j in range(4):
      case_n += 1
      events.append(
        {
          "safetyreportid": str(case_n),
          "serious": "2",
          "receiptdate": "20240215",
          "occurcountry": COUNTRIES[j % len(COUNTRIES)],
          "source_period": "2023q4" if j % 2 else "2024q1",
          "narrative": f"Background report: {ae} while on {name}.",
          "patient": {
            "patientsex": SEXES[j % 2],
            "patientonsetage": AGES[j % len(AGES)],
            "drug": [{"medicinalproduct": name.upper(), "drugcharacterization": "1", "drugdosagetext": dose}],
            "reaction": [{"reactionmeddrapt": ae, "reactionoutcome": "2"}],
          },
        }
      )
  _ = rng  # reserved for future jitter
  return events, case_n


def main() -> None:
  faers_path = FIXTURES / "faers.json"
  faers = json.loads(faers_path.read_text(encoding="utf-8"))
  case_n = 9500000
  for d in port.drugs:
    name = d["preferred_name"]
    events, case_n = build_faers_for(name, port.DOSES[name], port.PRIMARY_AES[name], case_n)
    faers[name] = events
    print(f"FAERS {name}: {len(events)} events")
  faers_path.write_text(json.dumps(faers, indent=2), encoding="utf-8")

  ob_path = FIXTURES / "orange_book.json"
  ob = json.loads(ob_path.read_text(encoding="utf-8"))
  for d in port.drugs:
    ob[d["drug_id"]] = {
      "nda_bla": d["nda_bla"],
      "applicant": d["sponsor_company"],
      "ingredient": d["preferred_name"],
      "trade_name": d["brand_name"],
      "molecule_type": d["molecule_type"],
      "source": "orange_book_openfda_fill",
    }
  ob_path.write_text(json.dumps(ob, indent=2), encoding="utf-8")

  eu_path = FIXTURES / "eudravigilance.json"
  eu = json.loads(eu_path.read_text(encoding="utf-8"))
  for d in port.drugs:
    primary = port.PRIMARY_AES[d["preferred_name"]]
    rows = []
    for i, ae in enumerate(primary[:2]):
      rows.append(
        {
          "case_id": f"EU-{d['drug_id'].replace('drug_', '').upper()[:6]}-{i+1:04d}",
          "ae": ae,
          "serious": ae in SERIOUS_AES,
          "country": ["DE", "FR", "IT", "ES", "NL"][i % 5],
          "report_date": f"2023-{(i % 9) + 1:02d}-15",
        }
      )
    eu[d["drug_id"]] = rows
  eu_path.write_text(json.dumps(eu, indent=2), encoding="utf-8")

  # ICTRP stubs for Global region coverage
  ic_path = FIXTURES / "ictrp_ctri.json"
  ic = json.loads(ic_path.read_text(encoding="utf-8"))
  for i, d in enumerate(port.drugs):
    ae = port.PRIMARY_AES[d["preferred_name"]][0]
    ic[d["drug_id"]] = {
      "trials": [
        {
          "registry_id": f"CTRI/2020/{(i % 12) + 1:02d}/0{30000 + i}",
          "source": "CTRI",
          "phase": "Phase 3",
          "country": "IN",
          "arms": [
            {
              "arm": port.DOSES[d["preferred_name"]],
              "ae": ae,
              "event_count": 8 + i,
              "subjects_at_risk": 400 + 50 * i,
              "median_onset_weeks": 2.0 + (i % 5),
              "global_cases": 4,
              "serious": ae in SERIOUS_AES,
            }
          ],
        }
      ]
    }
  ic_path.write_text(json.dumps(ic, indent=2), encoding="utf-8")
  print("Fixtures updated for", len(port.drugs), "portfolio drugs")


if __name__ == "__main__":
  main()
