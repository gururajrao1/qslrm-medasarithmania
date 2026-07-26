# QSLRM — MedasArithmania

**Hypothesis triage for drug safety signals.**

QSLRM ranks **drug ↔ adverse reaction** pairs and explains *why* a signal looks elevated — dose, off-target binding, transcriptomic stress, or genetics — so safety / translational teams can decide what to review next.

It is **not** a causality engine and **not** a replacement for Argus, Vault, or any regulated pharmacovigilance system. Disproportionality ≠ proven cause.

**Live demo:** [https://qslrm-medasarithmania.onrender.com](https://qslrm-medasarithmania.onrender.com)

> Free Render apps sleep when idle — the first load after a pause can take ~30–60 seconds.

---

## What this project does

Pharmacovigilance databases (like FAERS) often flag that a drug and a side effect appear together more than expected. That alone does not say **what to do**.

QSLRM turns those flags into a **ranked action queue**:

1. Pull public safety, trial, label, and multi-omic evidence for a set of drugs
2. Score each **drug–ADR pair** (ADR = adverse drug reaction)
3. Split the score into attribution percentages (dose / off-target / transcriptomic / genetic)
4. Flag pairs that are **rising** over recent reporting periods
5. Surface triage suggestions (dose review, genetic filter, protocol exclusion, DSUR-style export)

**Join grain:** always `drug ↔ target/gene ↔ MedDRA Preferred Term`. Never patient-level IDs.

---

## What you see in the UI

| Column / label | Meaning |
|----------------|---------|
| **Drug** | Preferred / generic name of the product |
| **Sponsor** | Marketing / applicant company |
| **ADR** | Adverse drug reaction as a MedDRA **PT** (Preferred Term), e.g. *Hepatotoxicity* |
| **Fused** | Overall triage score **0–100**. Higher = stronger combined evidence that this pair deserves review |
| **Flag** | Short action tag. **Rising** = the PV signal accelerated recently; other flags may mean dose / genetic / regulatory attention |
| **ΔROR** | Change in **Reporting Odds Ratio** across FAERS periods. Large positive ΔROR ≈ the disproportionate reporting is getting stronger |
| **Dose** | Share of the fused score attributed to **dose / exposure** risk |
| **Off** | Share attributed to **off-target** proteomic binding (ChEMBL / BindingDB-style affinities) |
| **Trans** | Share attributed to **transcriptomic** stress signatures (LINCS L1000-style) |
| **Gen** | Share attributed to **genetic / PGx** risk (ClinVar / PharmGKB-style metabolizer impact) |
| **N** | Number of supporting PV case–event links for this pair |

Attribution columns (**Dose / Off / Trans / Gen**) are percentages that roughly sum to 100%. They answer: *“If this pair is hot, what’s driving it?”*

### Other terms

| Term | Meaning |
|------|---------|
| **FAERS** | FDA Adverse Event Reporting System (US spontaneous reports via openFDA) |
| **ROR / PRR** | Disproportionality metrics — “reported together more than expected,” **not** proof of causation |
| **MedDRA PT** | Standard medical dictionary term for the reaction |
| **BBW** | Boxed warning on the US label |
| **DSUR** | Development Safety Update Report–style summary export (HTML) |
| **Pull all sources** | Cumulative refresh from wired public APIs / fixtures, then recompute scores |
| **CSV / DSUR** | Download audit table or a narrative safety summary |

---

## Example (how to read a row)

> *erlotinib · Roche / Genentech · Dermatitis acneiform · Fused 63.4 · Rising · ΔROR 19.97 · Dose 12% · Off 41% · Trans 28% · Gen 19% · N 1*

Plain English: this drug–rash pair scores mid-high for triage; the signal is **rising**; reporting odds moved up sharply; the model leans **off-target** more than dose or genetics. Treat that as a **hypothesis to review**, not a clinical conclusion.

---

## Data sources (wired)

Public / fixture-backed layers include:

- **PV:** openFDA FAERS, EudraVigilance fixtures  
- **Trials:** ClinicalTrials.gov, ICTRP / CTRI fixtures  
- **Labels / literature:** DailyMed / openFDA labels, PubMed, Europe PMC, SIDER, OnSIDES  
- **Multi-omic:** ChEMBL, BindingDB, LINCS, ClinVar / PharmGKB, Open Targets, Tox21, DepMap  
- **Regulatory context:** Orange Book / RxNorm sponsor–product mapping  

---

## Quick start (local)

```bash
git clone https://github.com/gururajrao1/qslrm-medasarithmania.git
cd qslrm-medasarithmania

python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -e ".[dev]"
cp .env.example .env
```

In `.env`:

```env
DATABASE_URL=sqlite:///./data/processed/qslrm.db
MODEL_VERSION=qslrm-v1.0.0
```

Build data and run:

```bash
python -m scripts.bootstrap_db
python -m scripts.seed_db
python -m scripts.run_phase1 --offline-dir tests/fixtures/phase1
python -m scripts.run_phase2
python -m scripts.run_phase3

uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

```bash
pytest -q
```

---

## Repo map

```
api/           HTTP API + serves the UI
web/           Action-queue frontend
qslrm_erd/     Database models & settings
ingest/        Source connectors & loaders
signals/       Disproportionality & velocity
omic_engine/   Multi-omic scores
fusion/        Fused score + decision cards
stream/        Event ledger / live updates
scripts/       Bootstrap, seed, phase runners
tests/         Pytest + offline fixtures
docs/          Deeper design notes
```

---

## License

MIT
