# QSLRM ERD (logical)

## Join grain

`drug` —(drug_target)— `target` —(pathway_target)— `pathway`
`drug` —(pv_drug_event)— `ae_term` ← openFDA PT string
`variant` related_pt ≈ `ae_term.pt_string`

No patient UUID. Crosswalks live in `ontology_crosswalk`.

## Tables

| Table | Purpose |
|-------|---------|
| drug | RxNorm + ChEMBL + ATC + MVP class flag |
| target | UniProt + Ensembl + gene symbol |
| drug_target | Ki/IC50, off-target flag |
| pathway / pathway_target | tox-tagged pathways |
| variant | ClinVar/ADME seeds for S_gen |
| ae_term | openFDA PT (+ optional MedDRA code later) |
| ontology_crosswalk | RxNorm↔ChEMBL, UniProt↔Ensembl, PT identity |
| pv_case / pv_drug_event | FAERS contingency facts |
| trial_ae | optional CT.gov AE counts |
| signal_stat | PRR/ROR/IC/EBGM by period |
| risk_score | fused 0–100 + attributions (seeded in Phase 2, fused in Phase 3) |
| omic_score | S_off / S_path / S_gen / omic_risk per drug–AE |
| ground_truth_label | BBW/REMS validation pairs |
