# MedasArithmania / QSLRM — Master System Prompt

> Enterprise translational multi-omic drug safety signal triage, streaming ingestion, & actionable decision platform.
> Join grain: `drug ↔ target/gene ↔ MedDRA/openFDA PT`. Never patient UUID.
> Claim boundary: disproportionality ≠ causality. Not an Argus/Vault replacement.

## Core purpose & philosophy

Hypothesis Triage & **Real-Time Decision Engine** at the intersection of Translational Bioinformatics (TBI), Computational Systems Pharmacology (CSP), Computational Pharmacovigilance, Pharmacogenomics (PGx), and FPGA/Hardware-Accelerated Bio-IT.

Concrete, audit-backed decisions:
**Dose Adjustment · Patient Stratification (Genetic Filtering) · Protocol Exclusion Clauses · Regulatory Response Exports.**

---

## 📦 Comprehensive Clinical & Multi-Omic Data Layer (Zero Blank Filters)

### 1. Company, Regulatory & Synthetic Cohort Layer
* **FDA Orange Book & Purple Book (FDA FTP/API):** Maps approved drug RxNorm/NDA/BLA IDs to sponsor companies, exclusivity dates, patent status, and molecule types (`Small Molecule` vs. `Biologic/MAb`).
* **Open SEC EDGAR API:** Parent company CIK, 10-K R&D disclosures, pipeline holdings across 20+ top sponsors (AstraZeneca, Bayer, BMS, BioNTech, Novartis, Pfizer, Roche, J&J, Merck, Sanofi, AbbVie, Eli Lilly, GSK, Takeda, Gilead, Amgen, Boehringer Ingelheim, Vertex, Biogen, Regeneron, Moderna).
* **DailyMed SPL Drug Labeling (NIH/NLM API):** Boxed Warnings, Contraindications, Adverse Reactions.
* **MedDRA Ontology Hierarchy (MSSO):** `SOC ↔ HLT ↔ PT` across FAERS, CT.gov, CTRI, EudraVigilance.
* **Synthea Synthetic Patient Engine:** FHIR/CSV synthetic EHR for exposure, dosing, co-morbidities, $t_{\text{onset}}$ (no PHI).

### 2. Clinical Trial Registries & Cohorts (Global & Company-Wise)
* **ClinicalTrials.gov API (v2) & CT-ADE / CT-ADE28:** Sponsor-filterable (`query.spons=…`); Phase I–IV, arms, N, AE counts.
* **CTRI & WHO ICTRP:** Global region + multi-country site analytics (EU CTIS / EudraCT aspirational live).
* **Trial data sharing:** Vivli, CSDR, YODA, sponsor CSR portals (aspirational).

### 3. Post-Market Pharmacovigilance & RWE
* **openFDA FAERS Bulk Quarterly Dumps & OpenVigilFDA:** Multi-period $\Delta\text{ROR}/\Delta t$.
* **EudraVigilance & WHO VigiBase:** `EU` / `Global` region filters.
* **Health Canada MedEffect & Australia TGA DAEN:** Cross-regional harmonization (aspirational).
* **Kidsides & age-risk benchmarks:** Pediatric / age-stratified FAERS enrichment.

### 4. Multi-Omics, Systems Biology & Structural
* **Proteomics:** ChEMBL & BindingDB (Ki/Kd/IC50, MoA, off-target).
* **Transcriptomics:** LINCS L1000 / CMap; TG-GATEs / DrugMatrix aspirational.
* **Genomics / PGx:** ClinVar, PharmGKB, CPIC (CYP metabolizer phenotypes).
* **Structural:** PDB & AlphaFold (pocket geometry; live pocket API later).
* **Pathways:** Open Targets / Reactome / KEGG; STRING, DepMap, HMDB, ToxCast/Tox21.
* **Literature NLP:** PubMed / Europe PMC, BioDEX, SIDER, OnSIDES, LP-SDA aspirational.

---

## ⚡ Real-Time Streaming & Cumulative Ingestion Architecture

```text
[ External APIs / Stream Workers ]
  (openFDA, CT.gov, CTRI, PubMed)
            │
            ▼
┌─────────────────────────────────┐
│ Append-Only Event Ledger Table  │  (raw_payload_json + SHA-256 hash)
└───────────┬─────────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│ CDC Bridge (MVP: poll / notify) │  Production: Debezium + Postgres logical
└───────────┬─────────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│ Julia & Python Engine Workers   │  (Incremental Fusion & ΔROR)
└───────────┬─────────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│ FastAPI WebSocket (/v1/stream)  │  (Live JSON patches → Frontend)
└─────────────────────────────────┘
```

### Implementation notes (this repo)
| Layer | MVP (SQLite) | Production target |
|-------|--------------|-------------------|
| Ledger | `event_ledger` append-only | Postgres same schema |
| CDC | In-process notify + cursor poll | Debezium → Kafka/NATS |
| Engines | Python workers; Julia optional | Julia + Python scale-out |
| Push | `WS /v1/stream` | Same + fan-out gateway |

---

## Hard join (`qslrm_erd`)

Ontology keys only. Core tables: `drug`, `target`, `drug_target`, `transcript_signature`, `variant`, `pathway`, `pv_case`, `pv_drug_event`, `trial_ae`, `risk_score`, `literature_evidence`, `side_effect_label`, **`event_ledger`**.

## UI

Frontpage action queue + drawer + **live stream chip** (WebSocket patches). Filters: sponsor (20+), molecule type, region (US/EU/Global), ΔROR sort.

## Engines

- Julia/Python omic: \(S_{omic}=\sigma(\alpha S_{off}+\beta S_{trans}+\gamma S_{gen})\)
- Fused risk · Signal velocity $\Delta$ROR · Attribution · `fusion/decisions.py`

## Phases

0 Schema/seed → 1 Ingest → 2 Engines → 3 Fusion/UI → 4 BBW validation & Docker → **5 Streaming ledger + WebSocket**
