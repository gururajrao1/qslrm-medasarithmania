"""Generate rich offline fixtures so the UI has substantial multi-omic / PV / CT data.

Run: python -m scripts.generate_rich_fixtures
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "fixtures" / "phase1"

DRUGS = [
  ("imatinib", "drug_imatinib", "CHEMBL941", "400 mg", "CYP3A4"),
  ("erlotinib", "drug_erlotinib", "CHEMBL553", "150 mg", "CYP3A4"),
  ("gefitinib", "drug_gefitinib", "CHEMBL939", "250 mg", "CYP3A4,CYP2D6"),
  ("dasatinib", "drug_dasatinib", "CHEMBL1421", "100 mg", "CYP3A4"),
  ("nilotinib", "drug_nilotinib", "CHEMBL1168", "300 mg BID", "CYP3A4"),
  ("sunitinib", "drug_sunitinib", "CHEMBL535", "50 mg", "CYP3A4"),
  ("sorafenib", "drug_sorafenib", "CHEMBL1336", "400 mg BID", "CYP3A4"),
  ("lapatinib", "drug_lapatinib", "CHEMBL554", "1250 mg", "CYP3A4,CYP2C8"),
  ("pazopanib", "drug_pazopanib", "CHEMBL119929", "800 mg", "CYP3A4"),
  ("axitinib", "drug_axitinib", "CHEMBL1289926", "5 mg BID", "CYP3A4,CYP1A2"),
  ("ibrutinib", "drug_ibrutinib", "CHEMBL1873475", "420 mg", "CYP3A4"),
  ("osimertinib", "drug_osimertinib", "CHEMBL3353410", "80 mg", "CYP3A4"),
  ("tofacitinib", "drug_tofacitinib", "CHEMBL221959", "5 mg BID", "CYP3A4,CYP2C19"),
]

# Primary AE profile per drug (high volume) + shared background AEs
PRIMARY_AE = {
  "imatinib": ["Nausea", "Rash", "Diarrhoea", "Hepatotoxicity"],
  "erlotinib": ["Rash", "Diarrhoea", "Interstitial lung disease", "Nausea"],
  "gefitinib": ["Rash", "Interstitial lung disease", "Diarrhoea", "Hepatotoxicity"],
  "dasatinib": ["Nausea", "Diarrhoea", "Rash", "Electrocardiogram QT prolonged"],
  "nilotinib": ["Electrocardiogram QT prolonged", "Hepatotoxicity", "Rash", "Nausea"],
  "sunitinib": ["Hypertension", "Palmar-plantar erythrodysaesthesia syndrome", "Nausea", "Diarrhoea"],
  "sorafenib": ["Palmar-plantar erythrodysaesthesia syndrome", "Hypertension", "Hepatotoxicity", "Diarrhoea"],
  "lapatinib": ["Hepatotoxicity", "Diarrhoea", "Rash", "Nausea"],
  "pazopanib": ["Hepatotoxicity", "Hypertension", "Diarrhoea", "Nausea"],
  "axitinib": ["Hypertension", "Diarrhoea", "Nausea", "Rash"],
  "ibrutinib": ["Nausea", "Diarrhoea", "Rash", "Hypertension"],
  "osimertinib": ["Rash", "Interstitial lung disease", "Diarrhoea", "Nausea"],
  "tofacitinib": ["Nausea", "Hypertension", "Diarrhoea", "Hepatotoxicity"],
}

ALL_AES = sorted({ae for aes in PRIMARY_AE.values() for ae in aes})

COUNTRIES = ["US", "JP", "DE", "GB", "FR", "CA", "AU", "IN", "BR", "KR"]
SEXES = ["1", "2"]
AGES = ["34", "48", "55", "62", "67", "71", "78"]

LINCS_GENES = [
  ("ABCB1", 0.8), ("ABCC2", 0.8), ("UGT1A1", 1.0), ("CYP3A4", 0.9), ("CYP2D6", 0.9),
  ("EGFR", 0.7), ("ERBB2", 0.7), ("IL6", 1.0), ("SFTPC", 1.1), ("ALT", 1.2),
  ("KCNH2", 1.3), ("VEGFA", 0.7), ("KRT14", 0.8), ("EDN1", 0.9), ("SOD1", 0.6),
  ("TNF", 1.0), ("HMOX1", 0.7), ("NQO1", 0.6), ("GSTA1", 0.8), ("SLCO1B1", 0.9),
  ("TP53", 0.5), ("MYC", 0.5), ("BAX", 0.6), ("BCL2", 0.6),
]

COMEDS = [
  ("ketoconazole", "6135", "CYP3A4"),
  ("clarithromycin", "21212", "CYP3A4"),
  ("omeprazole", "7646", "CYP2C19,CYP3A4"),
  ("simvastatin", "36567", "CYP3A4"),
  ("fluoxetine", "4493", "CYP2D6"),
  ("rifampin", "9384", "CYP3A4"),
  ("warfarin", "11289", "CYP2C9,CYP3A4"),
  ("amiodarone", "703", "CYP3A4,CYP2D6"),
]

CHEMBL_TARGETS = {
  "ABL1": ("CHEMBL1862", "P00519", "ENSG00000097007", "Tyrosine-protein kinase ABL"),
  "KIT": ("CHEMBL1936", "P10721", "ENSG00000157404", "Stem cell growth factor receptor"),
  "EGFR": ("CHEMBL203", "P00533", "ENSG00000146648", "Epidermal growth factor receptor"),
  "ERBB2": ("CHEMBL1824", "P04626", "ENSG00000141736", "Receptor tyrosine-protein kinase erbB-2"),
  "SRC": ("CHEMBL267", "P12931", "ENSG00000197122", "Proto-oncogene tyrosine-protein kinase Src"),
  "KDR": ("CHEMBL279", "P35968", "ENSG00000128052", "Vascular endothelial growth factor receptor 2"),
  "FLT1": ("CHEMBL1868", "P17948", "ENSG00000102755", "Vascular endothelial growth factor receptor 1"),
  "BRAF": ("CHEMBL5145", "P15056", "ENSG00000157764", "Serine/threonine-protein kinase B-raf"),
  "PDGFRA": ("CHEMBL2007", "P16234", "ENSG00000134853", "PDGF receptor alpha"),
  "CYP3A4": ("CHEMBL340", "P08684", "ENSG00000160868", "Cytochrome P450 3A4"),
}

# Primary + off-target gene lists per ChEMBL id
DRUG_GENES = {
  "CHEMBL941": [("ABL1", 25, False), ("KIT", 100, False), ("PDGFRA", 100, False), ("SRC", 450, True), ("EGFR", 800, True), ("CYP3A4", 1200, True)],
  "CHEMBL553": [("EGFR", 2, False), ("ERBB2", 350, True), ("SRC", 900, True), ("CYP3A4", 1500, True)],
  "CHEMBL939": [("EGFR", 3, False), ("ERBB2", 400, True), ("KIT", 1100, True), ("CYP3A4", 1400, True)],
  "CHEMBL1421": [("ABL1", 0.6, False), ("SRC", 0.5, False), ("KIT", 5, True), ("EGFR", 180, True), ("CYP3A4", 900, True)],
  "CHEMBL1168": [("ABL1", 20, False), ("KIT", 60, False), ("SRC", 200, True), ("CYP3A4", 1100, True)],
  "CHEMBL535": [("KDR", 10, False), ("KIT", 10, False), ("FLT1", 15, False), ("SRC", 500, True), ("CYP3A4", 1300, True)],
  "CHEMBL1336": [("BRAF", 38, False), ("KDR", 90, False), ("FLT1", 120, True), ("KIT", 68, True), ("CYP3A4", 1000, True)],
  "CHEMBL554": [("EGFR", 10.8, False), ("ERBB2", 9.2, False), ("SRC", 600, True), ("CYP3A4", 800, True)],
  "CHEMBL119929": [("KDR", 30, False), ("FLT1", 10, False), ("KIT", 74, True), ("CYP3A4", 1250, True)],
  "CHEMBL1289926": [("KDR", 0.2, False), ("FLT1", 0.1, False), ("KIT", 1.6, True), ("CYP3A4", 1100, True)],
}


def _km_points(acute: bool) -> list[dict]:
  if acute:
    weeks = [0, 0.5, 1, 2, 3, 4, 6, 8, 12]
    base = [1.0, 0.88, 0.75, 0.62, 0.55, 0.50, 0.46, 0.43, 0.41]
  else:
    weeks = [0, 2, 4, 6, 8, 10, 12, 16, 20]
    base = [1.0, 0.97, 0.93, 0.88, 0.82, 0.76, 0.71, 0.66, 0.62]
  return [{"week": w, "survival_prob": round(s, 3)} for w, s in zip(weeks, base)]


def build_faers() -> dict:
  rng = random.Random(42)
  out: dict[str, list] = {}
  case_n = 2000000
  for name, _did, _cid, dose, _cyp in DRUGS:
    events = []
    primary = PRIMARY_AE[name]
    # high-volume primary pairs
    for ae in primary:
      n_cases = 18 + rng.randint(0, 12)
      for j in range(n_cases):
        case_n += 1
        serious = "1" if (ae in {"Hepatotoxicity", "Interstitial lung disease", "Electrocardiogram QT prolonged"} or j % 3 == 0) else "2"
        sex = SEXES[(case_n + j) % 2]
        # enrichment: hepatotox more female 65+
        age = "71" if ae == "Hepatotoxicity" and j % 2 == 0 else AGES[(case_n + j) % len(AGES)]
        country = COUNTRIES[(case_n + j) % len(COUNTRIES)]
        period = "2024q1" if j % 2 == 0 else "2023q4"
        # secondary AE on some cases
        reactions = [{"reactionmeddrapt": ae, "reactionoutcome": "1" if serious == "1" else "2"}]
        if j % 4 == 0:
          reactions.append({"reactionmeddrapt": primary[(primary.index(ae) + 1) % len(primary)], "reactionoutcome": "2"})
        offlabel = " Off-label use noted." if j % 7 == 0 else ""
        events.append(
          {
            "safetyreportid": str(case_n),
            "serious": serious,
            "receiptdate": f"20240{(j % 9) + 1:02d}{(j % 27) + 1:02d}" if period == "2024q1" else f"2023{(10 + j % 3):02d}{(j % 27) + 1:02d}",
            "occurcountry": country,
            "source_period": period,
            "narrative": (
              f"Patient on {dose} {name} developed {ae} after {1 + j % 6} weeks."
              f"{offlabel} Dose timing noted; concomitant meds reviewed."
            ),
            "patient": {
              "patientsex": sex,
              "patientonsetage": age,
              "drug": [
                {
                  "medicinalproduct": name.upper(),
                  "drugcharacterization": "1",
                  "drugdosagetext": dose,
                }
              ],
              "reaction": reactions,
            },
          }
        )
    # sparse background AEs (still enough for some signals)
    for ae in ALL_AES:
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
            "narrative": f"Background report: {ae} while on {name} {dose}.",
            "patient": {
              "patientsex": SEXES[j % 2],
              "patientonsetage": AGES[j % len(AGES)],
              "drug": [{"medicinalproduct": name.upper(), "drugcharacterization": "1", "drugdosagetext": dose}],
              "reaction": [{"reactionmeddrapt": ae, "reactionoutcome": "2"}],
            },
          }
        )
    out[name] = events
  return out


def build_lincs() -> dict:
  rng = random.Random(7)
  out = {}
  for _name, did, _cid, _dose, _cyp in DRUGS:
    genes = []
    for i, (g, w) in enumerate(LINCS_GENES):
      z = rng.uniform(-3.2, 3.2)
      # amplify tox-relevant genes per drug family
      if "erlotinib" in did or "gefitinib" in did:
        if g in {"IL6", "SFTPC", "EGFR"}:
          z = abs(z) * (1 if g == "IL6" else -1)
      if "lapatinib" in did or "pazopanib" in did:
        if g in {"ALT", "UGT1A1", "CYP3A4"}:
          z = abs(z) if g != "CYP3A4" else -abs(z)
      if "nilotinib" in did and g == "KCNH2":
        z = -abs(z) - 1.5
      genes.append(
        {
          "gene_symbol": g,
          "z_score": round(z, 2),
          "tox_weight": w,
          "direction": "up" if z >= 0 else "down",
          "source": "lincs_fixture",
        }
      )
    out[did] = genes
  return out


def build_ctgov() -> dict:
  rng = random.Random(11)
  out = {}
  nct = 100
  for name, did, _cid, dose, cyp in DRUGS:
    trials = []
    for t_i, phase in enumerate(("Phase 2", "Phase 3")):
      nct += 1
      primary = PRIMARY_AE[name]
      arms = []
      for ae in primary[:3]:
        for mult, label in ((1.0, dose), (1.25, f"{dose} high")):
          arms.append(
            {
              "arm": label,
              "ae": ae,
              "event_count": int(8 + rng.randint(0, 20) * mult),
              "subjects_at_risk": int(80 + rng.randint(0, 60)),
              "median_onset_weeks": round(1.5 + rng.random() * 6, 1),
            }
          )
      comeds = [COMEDS[(nct + i) % len(COMEDS)] for i in range(3)]
      acute = primary[0] in {"Nausea", "Rash", "Diarrhoea"}
      trials.append(
        {
          "nct_id": f"NCT{nct:08d}",
          "phase": phase,
          "arms": arms,
          "concomitants": [
            {"name": c[0], "rxnorm": c[1], "cyp_enzymes": c[2]} for c in comeds
          ],
          "onset_curve": {"ae": primary[0], "points": _km_points(acute=acute)},
        }
      )
      # second onset curve for hepatic/QT where relevant
      if len(primary) > 1:
        trials[-1]["onset_curve_extra"] = {
          "ae": primary[1],
          "points": _km_points(acute=False),
        }
    out[did] = {"trials": trials}
  return out


def build_chembl() -> dict:
  out = {}
  for chembl_id, genes in DRUG_GENES.items():
    mechanisms = []
    activities = []
    targets = {}
    for gene, aff, _off in genes:
      tid, uniprot, ensembl, pref = CHEMBL_TARGETS[gene]
      mechanisms.append(
        {"molecule_chembl_id": chembl_id, "target_chembl_id": tid, "action_type": "INHIBITOR"}
      )
      activities.append(
        {
          "molecule_chembl_id": chembl_id,
          "target_chembl_id": tid,
          "standard_type": "IC50",
          "standard_value": aff,
          "standard_units": "nM",
        }
      )
      targets[tid] = {
        "pref_name": pref,
        "target_components": [
          {
            "gene_symbol": gene,
            "target_component_xrefs": [
              {"xref_src_db": "UniProt", "xref_id": uniprot},
              {"xref_src_db": "EnsemblGene", "xref_id": ensembl},
            ],
          }
        ],
      }
    out[chembl_id] = {"mechanisms": mechanisms, "activities": activities, "targets": targets}
  return out


def expand_ctgov_onset(payload: dict) -> dict:
  """ctgov loader only reads onset_curve; fold extras into separate trials if needed."""
  for did, block in payload.items():
    for trial in block.get("trials") or []:
      extra = trial.pop("onset_curve_extra", None)
      if extra:
        # attach as second trial clone for onset only — loader reads one onset_curve per trial
        block["trials"].append(
          {
            "nct_id": trial["nct_id"] + "B",
            "phase": trial.get("phase"),
            "arms": [
              {
                "arm": trial["arms"][0]["arm"] if trial.get("arms") else "standard",
                "ae": extra["ae"],
                "event_count": 10,
                "subjects_at_risk": 100,
                "median_onset_weeks": 5.0,
              }
            ],
            "concomitants": trial.get("concomitants") or [],
            "onset_curve": extra,
          }
        )
  return payload


def main() -> None:
  OUT.mkdir(parents=True, exist_ok=True)
  faers = build_faers()
  lincs = build_lincs()
  ctgov = expand_ctgov_onset(build_ctgov())
  chembl = build_chembl()

  (OUT / "faers.json").write_text(json.dumps(faers, indent=2), encoding="utf-8")
  (OUT / "lincs.json").write_text(json.dumps(lincs, indent=2), encoding="utf-8")
  (OUT / "ctgov.json").write_text(json.dumps(ctgov, indent=2), encoding="utf-8")
  (OUT / "chembl.json").write_text(json.dumps(chembl, indent=2), encoding="utf-8")

  n_cases = sum(len(v) for v in faers.values())
  n_lincs = sum(len(v) for v in lincs.values())
  n_trials = sum(len(b["trials"]) for b in ctgov.values())
  print(
    json.dumps(
      {
        "faers_cases": n_cases,
        "lincs_gene_rows": n_lincs,
        "ctgov_trials": n_trials,
        "chembl_drugs": len(chembl),
        "paths": {
          "faers": str(OUT / "faers.json"),
          "lincs": str(OUT / "lincs.json"),
          "ctgov": str(OUT / "ctgov.json"),
          "chembl": str(OUT / "chembl.json"),
        },
      },
      indent=2,
    )
  )


if __name__ == "__main__":
  main()
