# Literature NLP & Research Evidence Layer

Paste into the Comprehensive Data Layer of the Master System Prompt:

```markdown
#### 5. Literature NLP & Research Evidence Layer
* **PubMed & Europe PMC APIs:** Multi-tier PubMed → Europe PMC → Semantic Scholar cascade to extract biomedical literature evidence backing flagged drug–ADR pairs.
* **BioDEX & SIDER Datasets:** Standardized benchmarks for ADE extraction (BioDEX HF/GitHub) and package-insert side-effect frequencies × MedDRA PT (SIDER).
* **OnSIDES (Tatonetti lab):** PubMedBERT-extracted ADEs from DailyMed / EMA / EMC / KEGG labels — fresher multi-national complement to SIDER.
* **Open Targets Pharmacovigilance:** GraphQL `adverseEvents` LRT significant FAERS pairs (health-professional filtered) for cross-check vs local disproportionality.
* **openFDA Drug Labeling (SPL):** Adverse reactions / boxed-warning sections for label-vs-signal gap analysis.
* **Kidsides:** Pediatric age-stage FAERS enrichment for age-risk hypotheses (not causality).
* **Broad Drug Repurposing Hub:** Compound–target–phase dictionary hygiene for ~6k clinical molecules.
* **Pharma Sponsor Directory (20+ Companies):** Full sponsor mappings covering AstraZeneca, Bayer, BMS, Novartis, Pfizer, Roche, AbbVie, Eli Lilly, J&J, Merck, Sanofi, GSK, Takeda, Gilead, Amgen, Boehringer Ingelheim, plus biotech specialists (Vertex, Biogen, Regeneron, Moderna, BioNTech).
```

## Wired in QSLRM

| Source | Role | Mode | Approx rows (MVP rebuild) |
|--------|------|------|---------------------------|
| PubMed / Europe PMC | Literature cascade | live harvest → fixtures | ~170 papers |
| SIDER (`meddra_all_se.tsv.gz`) | Label side-effect PTs | real dump filtered to MVP | ~780 |
| OnSIDES v3.1.1 zip | PubMedBERT label ADEs | real release join | ~940 |
| Open Targets PV GraphQL | FAERS LRT | live API | ~340 |
| openFDA SPL | Label section matches | live harvest | ~40 |
| BioDEX / Kidsides | Benchmark / pediatric notes | fixtures | ~50 |

### Refresh fixtures from the net

```powershell
# SIDER dump (already under data/raw/) + OnSIDES zip (~85MB)
python -m scripts.fill_evidence_from_datasets
# optional: PubMed / Europe PMC / openFDA harvest
python -m scripts.harvest_evidence_fixtures
python -m scripts.run_phase1 --offline-dir tests/fixtures/phase1 --steps literature,sider,onsides,opentargets_pv,openfda_spl
```

## Claim boundary

Literature / label corroboration supports **hypothesis triage** only. Disproportionality ≠ causality.
