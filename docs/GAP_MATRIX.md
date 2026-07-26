# Gap matrix vs Master System Prompt

Status vs [MASTER_SYSTEM_PROMPT.md](MASTER_SYSTEM_PROMPT.md). Streaming details: [STREAMING.md](STREAMING.md).

| Layer | Item | Status |
|-------|------|--------|
| Regulatory | Orange Book / Purple Book IDs | PARTIAL (fixtures + sponsor portfolio) |
| Regulatory | SEC EDGAR CIK / 10-K | MISSING |
| Regulatory | DailyMed / openFDA SPL BBW | DONE |
| Regulatory | MedDRA SOC↔HLT↔PT | PARTIAL (fixture hierarchy) |
| Regulatory | Synthea $t_{\text{onset}}$ | PARTIAL (fixtures) |
| Omics | ChEMBL | DONE |
| Omics | BindingDB | PARTIAL (fixtures) |
| Omics | LINCS | DONE |
| Omics | TG-GATEs / DrugMatrix | MISSING |
| Omics | ClinVar | DONE |
| Omics | PharmGKB / CPIC | PARTIAL (seed) |
| Omics | PDB ids | PARTIAL (seed) |
| Omics | AlphaFold / STRING / HMDB | MISSING |
| Omics | Open Targets pathways | DONE |
| Omics | DepMap / Tox21 | PARTIAL (fixtures) |
| Trials | CT.gov v2 | PARTIAL (fixtures + sponsor live helper) |
| Trials | ICTRP / CTRI | PARTIAL (fixtures + Global PV) |
| Trials | CTIS / Vivli / YODA | MISSING |
| PV | openFDA FAERS | DONE |
| PV | EudraVigilance / OpenVigil | PARTIAL (fixtures) |
| PV | VigiBase / MedEffect / TGA | MISSING |
| PV | Kidsides | PARTIAL (notes) |
| Literature | PubMed / Europe PMC | DONE |
| Literature | SIDER / OnSIDES / OT PV | DONE |
| Literature | BioDEX | PARTIAL |
| Literature | LP-SDA | MISSING |
| UI | Queue + drawer + tabs | DONE |
| UI | 20+ sponsors (all populated) | DONE |
| UI | Molecule / region filters | DONE |
| UI | Live WebSocket chip | DONE (MVP) |
| Engines | PRR/ROR / ΔROR / fusion | DONE |
| Engines | Julia omic | PARTIAL (Python truth) |
| Streaming | Append-only `event_ledger` + SHA-256 | DONE (MVP) |
| Streaming | Debezium / Postgres CDC | MISSING (prod path) |
| Streaming | WS `/v1/stream` | DONE (MVP) |
| Phase 4 | BBW enrichment gate | DONE |
