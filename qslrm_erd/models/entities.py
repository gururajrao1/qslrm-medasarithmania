"""Core ontology + PV + scoring + decision-platform tables for QSLRM.

Join grain (MVP): drug ↔ target/gene ↔ MedDRA/openFDA PT — never patient UUID.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
  Boolean,
  Date,
  DateTime,
  Float,
  ForeignKey,
  Index,
  Integer,
  String,
  Text,
  UniqueConstraint,
  func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from qslrm_erd.models.base import Base


class Drug(Base):
  __tablename__ = "drug"

  drug_id: Mapped[str] = mapped_column(String(64), primary_key=True)
  preferred_name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
  brand_name: Mapped[Optional[str]] = mapped_column(String(128))
  drug_class: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
  therapeutic_class: Mapped[Optional[str]] = mapped_column(String(64), index=True)
  molecule_type: Mapped[str] = mapped_column(String(32), default="small_molecule", nullable=False, index=True)
  sponsor_company: Mapped[Optional[str]] = mapped_column(String(128), index=True)
  nda_bla: Mapped[Optional[str]] = mapped_column(String(32))
  atc_code: Mapped[Optional[str]] = mapped_column(String(32))
  rxnorm_cui: Mapped[Optional[str]] = mapped_column(String(32), index=True)
  chembl_id: Mapped[Optional[str]] = mapped_column(String(32), index=True)
  is_mvp_seed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  cyp_substrates: Mapped[Optional[str]] = mapped_column(String(256))  # e.g. CYP3A4,CYP2D6
  notes: Mapped[Optional[str]] = mapped_column(Text)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

  targets: Mapped[list[DrugTarget]] = relationship(back_populates="drug")


class Target(Base):
  __tablename__ = "target"

  target_id: Mapped[str] = mapped_column(String(64), primary_key=True)
  gene_symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
  uniprot_id: Mapped[Optional[str]] = mapped_column(String(32), index=True)
  ensembl_id: Mapped[Optional[str]] = mapped_column(String(32), index=True)
  pdb_id: Mapped[Optional[str]] = mapped_column(String(16))
  protein_name: Mapped[Optional[str]] = mapped_column(String(256))
  is_admet_relevant: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

  drugs: Mapped[list[DrugTarget]] = relationship(back_populates="target")


class DrugTarget(Base):
  __tablename__ = "drug_target"
  __table_args__ = (UniqueConstraint("drug_id", "target_id", name="uq_drug_target"),)

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  drug_id: Mapped[str] = mapped_column(ForeignKey("drug.drug_id"), nullable=False, index=True)
  target_id: Mapped[str] = mapped_column(ForeignKey("target.target_id"), nullable=False, index=True)
  affinity_nm: Mapped[Optional[float]] = mapped_column(Float)
  affinity_type: Mapped[Optional[str]] = mapped_column(String(16))
  action_type: Mapped[Optional[str]] = mapped_column(String(64))
  is_off_target: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  source: Mapped[str] = mapped_column(String(64), default="chembl", nullable=False)

  drug: Mapped[Drug] = relationship(back_populates="targets")
  target: Mapped[Target] = relationship(back_populates="drugs")


class Pathway(Base):
  __tablename__ = "pathway"

  pathway_id: Mapped[str] = mapped_column(String(64), primary_key=True)
  name: Mapped[str] = mapped_column(String(256), nullable=False)
  source: Mapped[str] = mapped_column(String(64), default="opentargets", nullable=False)
  tox_tag: Mapped[Optional[str]] = mapped_column(String(64))


class PathwayTarget(Base):
  __tablename__ = "pathway_target"
  __table_args__ = (UniqueConstraint("pathway_id", "target_id", name="uq_pathway_target"),)

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  pathway_id: Mapped[str] = mapped_column(ForeignKey("pathway.pathway_id"), nullable=False)
  target_id: Mapped[str] = mapped_column(ForeignKey("target.target_id"), nullable=False)


class Variant(Base):
  __tablename__ = "variant"

  variant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
  rsid: Mapped[Optional[str]] = mapped_column(String(32), index=True)
  gene_symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
  clinvar_id: Mapped[Optional[str]] = mapped_column(String(32))
  pharmgkb_id: Mapped[Optional[str]] = mapped_column(String(64))
  metabolizer_impact: Mapped[Optional[str]] = mapped_column(String(64))  # e.g. CYP2D6_PM
  consequence: Mapped[Optional[str]] = mapped_column(String(128))
  allele_freq: Mapped[Optional[float]] = mapped_column(Float)
  effect_size: Mapped[Optional[float]] = mapped_column(Float)
  related_pt: Mapped[Optional[str]] = mapped_column(String(128), index=True)
  notes: Mapped[Optional[str]] = mapped_column(Text)


class TranscriptSignature(Base):
  """LINCS L1000 / CMap-style gene perturbation z-scores per drug."""

  __tablename__ = "transcript_signature"
  __table_args__ = (
    UniqueConstraint("drug_id", "gene_symbol", "source", name="uq_transcript_sig"),
  )

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  drug_id: Mapped[str] = mapped_column(ForeignKey("drug.drug_id"), nullable=False, index=True)
  gene_symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
  z_score: Mapped[float] = mapped_column(Float, nullable=False)
  tox_weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
  direction: Mapped[Optional[str]] = mapped_column(String(16))  # up | down
  source: Mapped[str] = mapped_column(String(64), default="lincs_fixture", nullable=False)


class AeTerm(Base):
  __tablename__ = "ae_term"

  ae_term_id: Mapped[str] = mapped_column(String(64), primary_key=True)
  pt_string: Mapped[str] = mapped_column(String(256), nullable=False, unique=True, index=True)
  meddra_pt_code: Mapped[Optional[str]] = mapped_column(String(32), index=True)
  meddra_hlt: Mapped[Optional[str]] = mapped_column(String(128))
  meddra_hlt_code: Mapped[Optional[str]] = mapped_column(String(32), index=True)
  meddra_soc_code: Mapped[Optional[str]] = mapped_column(String(32), index=True)
  soc: Mapped[Optional[str]] = mapped_column(String(128))
  snomed_id: Mapped[Optional[str]] = mapped_column(String(64))
  hpo_id: Mapped[Optional[str]] = mapped_column(String(32))
  source: Mapped[str] = mapped_column(String(64), default="openfda_pt", nullable=False)


class OntologyCrosswalk(Base):
  __tablename__ = "ontology_crosswalk"
  __table_args__ = (
    UniqueConstraint(
      "entity_type", "from_system", "from_id", "to_system", "to_id", name="uq_crosswalk"
    ),
  )

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
  from_system: Mapped[str] = mapped_column(String(32), nullable=False)
  from_id: Mapped[str] = mapped_column(String(128), nullable=False)
  to_system: Mapped[str] = mapped_column(String(32), nullable=False)
  to_id: Mapped[str] = mapped_column(String(128), nullable=False)
  confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)


class PvCase(Base):
  __tablename__ = "pv_case"

  case_id: Mapped[str] = mapped_column(String(64), primary_key=True)
  report_date: Mapped[Optional[date]] = mapped_column(Date)
  country: Mapped[Optional[str]] = mapped_column(String(8))
  source_region: Mapped[Optional[str]] = mapped_column(String(16), index=True)  # US | EU | Global
  sex: Mapped[Optional[str]] = mapped_column(String(16))
  age_group: Mapped[Optional[str]] = mapped_column(String(32))
  serious: Mapped[Optional[bool]] = mapped_column(Boolean)
  outcome: Mapped[Optional[str]] = mapped_column(String(64))
  source_period: Mapped[Optional[str]] = mapped_column(String(16))
  narrative: Mapped[Optional[str]] = mapped_column(Text)


class PvDrugEvent(Base):
  __tablename__ = "pv_drug_event"
  __table_args__ = (
    UniqueConstraint("case_id", "drug_id", "ae_term_id", name="uq_pv_drug_event"),
    Index("ix_pv_drug_ae", "drug_id", "ae_term_id"),
  )

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  case_id: Mapped[str] = mapped_column(ForeignKey("pv_case.case_id"), nullable=False)
  drug_id: Mapped[str] = mapped_column(ForeignKey("drug.drug_id"), nullable=False, index=True)
  ae_term_id: Mapped[str] = mapped_column(ForeignKey("ae_term.ae_term_id"), nullable=False)
  drug_role: Mapped[Optional[str]] = mapped_column(String(8))
  dose_text: Mapped[Optional[str]] = mapped_column(String(256))
  dose_proxy: Mapped[Optional[float]] = mapped_column(Float)


class NarrativeEntity(Base):
  """NLP-extracted clinical entities from FAERS narratives (rule/BERT upgrade path)."""

  __tablename__ = "narrative_entity"
  __table_args__ = (Index("ix_narrative_case", "case_id"),)

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  case_id: Mapped[str] = mapped_column(ForeignKey("pv_case.case_id"), nullable=False)
  drug_id: Mapped[Optional[str]] = mapped_column(ForeignKey("drug.drug_id"))
  entity_type: Mapped[str] = mapped_column(String(64), nullable=False)  # symptom|dose|offlabel|timing
  entity_text: Mapped[str] = mapped_column(String(256), nullable=False)
  confidence: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
  extractor: Mapped[str] = mapped_column(String(64), default="rule_nlp", nullable=False)


class TrialAe(Base):
  __tablename__ = "trial_ae"
  __table_args__ = (UniqueConstraint("nct_id", "arm", "ae_term_id", name="uq_trial_ae"),)

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  nct_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
  drug_id: Mapped[Optional[str]] = mapped_column(ForeignKey("drug.drug_id"))
  phase: Mapped[Optional[str]] = mapped_column(String(16))
  arm: Mapped[str] = mapped_column(String(128), nullable=False)
  ae_term_id: Mapped[str] = mapped_column(ForeignKey("ae_term.ae_term_id"), nullable=False)
  event_count: Mapped[Optional[int]] = mapped_column(Integer)
  subjects_at_risk: Mapped[Optional[int]] = mapped_column(Integer)
  dose_text: Mapped[Optional[str]] = mapped_column(String(256))
  median_onset_weeks: Mapped[Optional[float]] = mapped_column(Float)


class TrialOnsetCurve(Base):
  """Discretized Kaplan-Meier-style survival points for AE time-to-onset."""

  __tablename__ = "trial_onset_curve"
  __table_args__ = (
    UniqueConstraint("drug_id", "ae_term_id", "week", "nct_id", name="uq_onset_curve"),
  )

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  drug_id: Mapped[str] = mapped_column(ForeignKey("drug.drug_id"), nullable=False, index=True)
  ae_term_id: Mapped[str] = mapped_column(ForeignKey("ae_term.ae_term_id"), nullable=False)
  nct_id: Mapped[str] = mapped_column(String(32), nullable=False)
  week: Mapped[float] = mapped_column(Float, nullable=False)
  survival_prob: Mapped[float] = mapped_column(Float, nullable=False)  # P(no AE yet)
  event_prob: Mapped[float] = mapped_column(Float, nullable=False)  # 1 - survival


class TrialConcomitant(Base):
  __tablename__ = "trial_concomitant"
  __table_args__ = (
    UniqueConstraint("nct_id", "drug_id", "concomitant_name", name="uq_trial_comed"),
  )

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  nct_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
  drug_id: Mapped[str] = mapped_column(ForeignKey("drug.drug_id"), nullable=False)
  concomitant_name: Mapped[str] = mapped_column(String(128), nullable=False)
  concomitant_rxnorm: Mapped[Optional[str]] = mapped_column(String(32))
  cyp_enzymes: Mapped[Optional[str]] = mapped_column(String(128))


class DdiRisk(Base):
  __tablename__ = "ddi_risk"
  __table_args__ = (
    UniqueConstraint("drug_id", "concomitant_name", "enzyme", name="uq_ddi_risk"),
  )

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  drug_id: Mapped[str] = mapped_column(ForeignKey("drug.drug_id"), nullable=False, index=True)
  concomitant_name: Mapped[str] = mapped_column(String(128), nullable=False)
  enzyme: Mapped[str] = mapped_column(String(32), nullable=False)
  risk_level: Mapped[str] = mapped_column(String(16), nullable=False)  # high|moderate|low
  mechanism: Mapped[str] = mapped_column(String(128), nullable=False)
  notes: Mapped[Optional[str]] = mapped_column(Text)


class SignalStat(Base):
  __tablename__ = "signal_stat"
  __table_args__ = (
    UniqueConstraint("drug_id", "ae_term_id", "period", "model_version", name="uq_signal_stat"),
  )

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  drug_id: Mapped[str] = mapped_column(ForeignKey("drug.drug_id"), nullable=False, index=True)
  ae_term_id: Mapped[str] = mapped_column(ForeignKey("ae_term.ae_term_id"), nullable=False)
  period: Mapped[str] = mapped_column(String(16), nullable=False, default="all")
  n11: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  n1_: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  n_1: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  n__: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  prr: Mapped[Optional[float]] = mapped_column(Float)
  ror: Mapped[Optional[float]] = mapped_column(Float)
  ror_ci_low: Mapped[Optional[float]] = mapped_column(Float)
  ror_ci_high: Mapped[Optional[float]] = mapped_column(Float)
  ic: Mapped[Optional[float]] = mapped_column(Float)
  ebgm: Mapped[Optional[float]] = mapped_column(Float)
  serious_rate: Mapped[Optional[float]] = mapped_column(Float)
  model_version: Mapped[str] = mapped_column(String(32), nullable=False)
  computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SignalVelocity(Base):
  """ΔROR / Δt across FAERS periods — rising signal detection."""

  __tablename__ = "signal_velocity"
  __table_args__ = (
    UniqueConstraint("drug_id", "ae_term_id", "period_from", "period_to", "model_version", name="uq_velocity"),
  )

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  drug_id: Mapped[str] = mapped_column(ForeignKey("drug.drug_id"), nullable=False, index=True)
  ae_term_id: Mapped[str] = mapped_column(ForeignKey("ae_term.ae_term_id"), nullable=False)
  period_from: Mapped[str] = mapped_column(String(16), nullable=False)
  period_to: Mapped[str] = mapped_column(String(16), nullable=False)
  ror_from: Mapped[float] = mapped_column(Float, nullable=False)
  ror_to: Mapped[float] = mapped_column(Float, nullable=False)
  delta_ror: Mapped[float] = mapped_column(Float, nullable=False)
  velocity: Mapped[float] = mapped_column(Float, nullable=False)  # delta_ror / quarters
  rising: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  model_version: Mapped[str] = mapped_column(String(32), nullable=False)


class DemographicSignal(Base):
  __tablename__ = "demographic_signal"
  __table_args__ = (
    UniqueConstraint(
      "drug_id", "ae_term_id", "stratum_type", "stratum_value", "model_version", name="uq_demo_sig"
    ),
  )

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  drug_id: Mapped[str] = mapped_column(ForeignKey("drug.drug_id"), nullable=False, index=True)
  ae_term_id: Mapped[str] = mapped_column(ForeignKey("ae_term.ae_term_id"), nullable=False)
  stratum_type: Mapped[str] = mapped_column(String(32), nullable=False)  # sex|age_group|country
  stratum_value: Mapped[str] = mapped_column(String(64), nullable=False)
  n_reports: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  share: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
  lift_vs_background: Mapped[Optional[float]] = mapped_column(Float)
  model_version: Mapped[str] = mapped_column(String(32), nullable=False)


class RiskScore(Base):
  __tablename__ = "risk_score"
  __table_args__ = (
    UniqueConstraint("drug_id", "ae_term_id", "model_version", name="uq_risk_score"),
  )

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  drug_id: Mapped[str] = mapped_column(ForeignKey("drug.drug_id"), nullable=False, index=True)
  ae_term_id: Mapped[str] = mapped_column(ForeignKey("ae_term.ae_term_id"), nullable=False)
  n_reports: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  prr: Mapped[Optional[float]] = mapped_column(Float)
  ror: Mapped[Optional[float]] = mapped_column(Float)
  omic_risk: Mapped[Optional[float]] = mapped_column(Float)
  dose_risk: Mapped[Optional[float]] = mapped_column(Float)
  serious_rate: Mapped[Optional[float]] = mapped_column(Float)
  fused_score: Mapped[Optional[float]] = mapped_column(Float)
  attr_dose: Mapped[Optional[float]] = mapped_column(Float)
  attr_offtarget: Mapped[Optional[float]] = mapped_column(Float)
  attr_transcriptomic: Mapped[Optional[float]] = mapped_column(Float)
  attr_genetic: Mapped[Optional[float]] = mapped_column(Float)
  action_needed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  action_flag: Mapped[Optional[str]] = mapped_column(String(64))
  rising_signal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  model_version: Mapped[str] = mapped_column(String(32), nullable=False)
  computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OmicScore(Base):
  __tablename__ = "omic_score"
  __table_args__ = (
    UniqueConstraint("drug_id", "ae_term_id", "model_version", name="uq_omic_score"),
  )

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  drug_id: Mapped[str] = mapped_column(ForeignKey("drug.drug_id"), nullable=False, index=True)
  ae_term_id: Mapped[str] = mapped_column(ForeignKey("ae_term.ae_term_id"), nullable=False)
  s_off: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
  s_path: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
  s_trans: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
  s_gen: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
  omic_risk: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
  engine: Mapped[str] = mapped_column(String(32), nullable=False, default="python")
  model_version: Mapped[str] = mapped_column(String(32), nullable=False)
  computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProtocolExclusion(Base):
  """Auto-generated Phase III exclusion clause suggestions from genetic drivers."""

  __tablename__ = "protocol_exclusion"
  __table_args__ = (
    UniqueConstraint("drug_id", "ae_term_id", "variant_id", name="uq_protocol_excl"),
  )

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  drug_id: Mapped[str] = mapped_column(ForeignKey("drug.drug_id"), nullable=False)
  ae_term_id: Mapped[str] = mapped_column(ForeignKey("ae_term.ae_term_id"), nullable=False)
  variant_id: Mapped[Optional[str]] = mapped_column(ForeignKey("variant.variant_id"))
  clause_text: Mapped[str] = mapped_column(Text, nullable=False)
  rationale: Mapped[str] = mapped_column(Text, nullable=False)
  estimated_adr_reduction: Mapped[Optional[float]] = mapped_column(Float)


class LiteratureEvidence(Base):
  """PubMed / Europe PMC / Semantic Scholar evidence backing a drug–ADR pair."""

  __tablename__ = "literature_evidence"
  __table_args__ = (
    UniqueConstraint("drug_id", "ae_term_id", "pmid", "source", name="uq_lit_evidence"),
  )

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  drug_id: Mapped[str] = mapped_column(ForeignKey("drug.drug_id"), nullable=False, index=True)
  ae_term_id: Mapped[str] = mapped_column(ForeignKey("ae_term.ae_term_id"), nullable=False)
  pmid: Mapped[str] = mapped_column(String(32), nullable=False)
  title: Mapped[str] = mapped_column(String(512), nullable=False)
  year: Mapped[Optional[int]] = mapped_column(Integer)
  source: Mapped[str] = mapped_column(String(32), nullable=False, default="pubmed")
  citation_count: Mapped[Optional[int]] = mapped_column(Integer)
  abstract_snippet: Mapped[Optional[str]] = mapped_column(Text)
  relation_confirmed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
  extractor: Mapped[str] = mapped_column(String(64), default="fixture", nullable=False)


class SideEffectLabel(Base):
  """SIDER-style package-insert side effect frequency (label evidence)."""

  __tablename__ = "side_effect_label"
  __table_args__ = (
    UniqueConstraint("drug_id", "ae_term_id", "source", name="uq_sider_label"),
  )

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  drug_id: Mapped[str] = mapped_column(ForeignKey("drug.drug_id"), nullable=False, index=True)
  ae_term_id: Mapped[str] = mapped_column(ForeignKey("ae_term.ae_term_id"), nullable=False)
  frequency: Mapped[Optional[str]] = mapped_column(String(64))  # common|uncommon|rare|postmarketing
  source: Mapped[str] = mapped_column(String(32), default="sider", nullable=False)


class GroundTruthLabel(Base):
  __tablename__ = "ground_truth_label"
  __table_args__ = (UniqueConstraint("drug_id", "ae_term_id", "label_type", name="uq_gt_label"),)

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  drug_id: Mapped[str] = mapped_column(ForeignKey("drug.drug_id"), nullable=False)
  ae_term_id: Mapped[str] = mapped_column(ForeignKey("ae_term.ae_term_id"), nullable=False)
  label_type: Mapped[str] = mapped_column(String(32), nullable=False)
  source: Mapped[str] = mapped_column(String(128), nullable=False)
  notes: Mapped[Optional[str]] = mapped_column(Text)


class EventLedger(Base):
  """Append-only ingestion ledger (stream MVP). Production: Postgres + Debezium CDC.

  Join grain remains ontology keys — never patient UUID. Payload is raw JSON from
  openFDA / CT.gov / CTRI / PubMed workers; content-addressed via SHA-256.
  """

  __tablename__ = "event_ledger"
  __table_args__ = (
    UniqueConstraint("source", "entity_key", "payload_sha256", name="uq_event_ledger_hash"),
    Index("ix_event_ledger_source_ts", "source", "created_at"),
  )

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
  entity_key: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
  drug_id: Mapped[Optional[str]] = mapped_column(ForeignKey("drug.drug_id"), index=True)
  ae_term_id: Mapped[Optional[str]] = mapped_column(ForeignKey("ae_term.ae_term_id"), index=True)
  event_type: Mapped[str] = mapped_column(String(64), nullable=False, default="ingest")
  payload_json: Mapped[str] = mapped_column(Text, nullable=False)
  payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
  summary: Mapped[Optional[str]] = mapped_column(String(512))
  created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
