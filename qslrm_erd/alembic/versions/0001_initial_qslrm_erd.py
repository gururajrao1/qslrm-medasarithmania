"""Initial qslrm_erd schema — ontology spine + PV + scores.

Revision ID: 0001_initial_qslrm_erd
Revises:
Create Date: 2026-07-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_qslrm_erd"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
  op.create_table(
    "drug",
    sa.Column("drug_id", sa.String(length=64), nullable=False),
    sa.Column("preferred_name", sa.String(length=256), nullable=False),
    sa.Column("drug_class", sa.String(length=64), nullable=False),
    sa.Column("atc_code", sa.String(length=32), nullable=True),
    sa.Column("rxnorm_cui", sa.String(length=32), nullable=True),
    sa.Column("chembl_id", sa.String(length=32), nullable=True),
    sa.Column("is_mvp_seed", sa.Boolean(), nullable=False),
    sa.Column("notes", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.PrimaryKeyConstraint("drug_id"),
  )
  op.create_index("ix_drug_preferred_name", "drug", ["preferred_name"])
  op.create_index("ix_drug_drug_class", "drug", ["drug_class"])
  op.create_index("ix_drug_rxnorm_cui", "drug", ["rxnorm_cui"])
  op.create_index("ix_drug_chembl_id", "drug", ["chembl_id"])

  op.create_table(
    "target",
    sa.Column("target_id", sa.String(length=64), nullable=False),
    sa.Column("gene_symbol", sa.String(length=64), nullable=False),
    sa.Column("uniprot_id", sa.String(length=32), nullable=True),
    sa.Column("ensembl_id", sa.String(length=32), nullable=True),
    sa.Column("protein_name", sa.String(length=256), nullable=True),
    sa.Column("is_admet_relevant", sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint("target_id"),
  )
  op.create_index("ix_target_gene_symbol", "target", ["gene_symbol"])
  op.create_index("ix_target_uniprot_id", "target", ["uniprot_id"])
  op.create_index("ix_target_ensembl_id", "target", ["ensembl_id"])

  op.create_table(
    "pathway",
    sa.Column("pathway_id", sa.String(length=64), nullable=False),
    sa.Column("name", sa.String(length=256), nullable=False),
    sa.Column("source", sa.String(length=64), nullable=False),
    sa.Column("tox_tag", sa.String(length=64), nullable=True),
    sa.PrimaryKeyConstraint("pathway_id"),
  )

  op.create_table(
    "variant",
    sa.Column("variant_id", sa.String(length=64), nullable=False),
    sa.Column("rsid", sa.String(length=32), nullable=True),
    sa.Column("gene_symbol", sa.String(length=64), nullable=False),
    sa.Column("clinvar_id", sa.String(length=32), nullable=True),
    sa.Column("consequence", sa.String(length=128), nullable=True),
    sa.Column("allele_freq", sa.Float(), nullable=True),
    sa.Column("effect_size", sa.Float(), nullable=True),
    sa.Column("related_pt", sa.String(length=128), nullable=True),
    sa.Column("notes", sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint("variant_id"),
  )
  op.create_index("ix_variant_rsid", "variant", ["rsid"])
  op.create_index("ix_variant_gene_symbol", "variant", ["gene_symbol"])
  op.create_index("ix_variant_related_pt", "variant", ["related_pt"])

  op.create_table(
    "ae_term",
    sa.Column("ae_term_id", sa.String(length=64), nullable=False),
    sa.Column("pt_string", sa.String(length=256), nullable=False),
    sa.Column("meddra_pt_code", sa.String(length=32), nullable=True),
    sa.Column("soc", sa.String(length=128), nullable=True),
    sa.Column("snomed_id", sa.String(length=64), nullable=True),
    sa.Column("hpo_id", sa.String(length=32), nullable=True),
    sa.Column("source", sa.String(length=64), nullable=False),
    sa.PrimaryKeyConstraint("ae_term_id"),
    sa.UniqueConstraint("pt_string"),
  )
  op.create_index("ix_ae_term_pt_string", "ae_term", ["pt_string"])
  op.create_index("ix_ae_term_meddra_pt_code", "ae_term", ["meddra_pt_code"])

  op.create_table(
    "ontology_crosswalk",
    sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("entity_type", sa.String(length=32), nullable=False),
    sa.Column("from_system", sa.String(length=32), nullable=False),
    sa.Column("from_id", sa.String(length=128), nullable=False),
    sa.Column("to_system", sa.String(length=32), nullable=False),
    sa.Column("to_id", sa.String(length=128), nullable=False),
    sa.Column("confidence", sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint(
      "entity_type", "from_system", "from_id", "to_system", "to_id", name="uq_crosswalk"
    ),
  )

  op.create_table(
    "pv_case",
    sa.Column("case_id", sa.String(length=64), nullable=False),
    sa.Column("report_date", sa.Date(), nullable=True),
    sa.Column("country", sa.String(length=8), nullable=True),
    sa.Column("serious", sa.Boolean(), nullable=True),
    sa.Column("outcome", sa.String(length=64), nullable=True),
    sa.Column("source_period", sa.String(length=16), nullable=True),
    sa.PrimaryKeyConstraint("case_id"),
  )

  op.create_table(
    "drug_target",
    sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("drug_id", sa.String(length=64), nullable=False),
    sa.Column("target_id", sa.String(length=64), nullable=False),
    sa.Column("affinity_nm", sa.Float(), nullable=True),
    sa.Column("affinity_type", sa.String(length=16), nullable=True),
    sa.Column("action_type", sa.String(length=64), nullable=True),
    sa.Column("is_off_target", sa.Boolean(), nullable=False),
    sa.Column("source", sa.String(length=64), nullable=False),
    sa.ForeignKeyConstraint(["drug_id"], ["drug.drug_id"]),
    sa.ForeignKeyConstraint(["target_id"], ["target.target_id"]),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("drug_id", "target_id", name="uq_drug_target"),
  )
  op.create_index("ix_drug_target_drug_id", "drug_target", ["drug_id"])
  op.create_index("ix_drug_target_target_id", "drug_target", ["target_id"])

  op.create_table(
    "pathway_target",
    sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("pathway_id", sa.String(length=64), nullable=False),
    sa.Column("target_id", sa.String(length=64), nullable=False),
    sa.ForeignKeyConstraint(["pathway_id"], ["pathway.pathway_id"]),
    sa.ForeignKeyConstraint(["target_id"], ["target.target_id"]),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("pathway_id", "target_id", name="uq_pathway_target"),
  )

  op.create_table(
    "pv_drug_event",
    sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("case_id", sa.String(length=64), nullable=False),
    sa.Column("drug_id", sa.String(length=64), nullable=False),
    sa.Column("ae_term_id", sa.String(length=64), nullable=False),
    sa.Column("drug_role", sa.String(length=8), nullable=True),
    sa.Column("dose_text", sa.String(length=256), nullable=True),
    sa.Column("dose_proxy", sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(["ae_term_id"], ["ae_term.ae_term_id"]),
    sa.ForeignKeyConstraint(["case_id"], ["pv_case.case_id"]),
    sa.ForeignKeyConstraint(["drug_id"], ["drug.drug_id"]),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("case_id", "drug_id", "ae_term_id", name="uq_pv_drug_event"),
  )
  op.create_index("ix_pv_drug_event_drug_id", "pv_drug_event", ["drug_id"])
  op.create_index("ix_pv_drug_ae", "pv_drug_event", ["drug_id", "ae_term_id"])

  op.create_table(
    "trial_ae",
    sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("nct_id", sa.String(length=32), nullable=False),
    sa.Column("drug_id", sa.String(length=64), nullable=True),
    sa.Column("arm", sa.String(length=128), nullable=False),
    sa.Column("ae_term_id", sa.String(length=64), nullable=False),
    sa.Column("event_count", sa.Integer(), nullable=True),
    sa.Column("subjects_at_risk", sa.Integer(), nullable=True),
    sa.Column("dose_text", sa.String(length=256), nullable=True),
    sa.ForeignKeyConstraint(["ae_term_id"], ["ae_term.ae_term_id"]),
    sa.ForeignKeyConstraint(["drug_id"], ["drug.drug_id"]),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("nct_id", "arm", "ae_term_id", name="uq_trial_ae"),
  )
  op.create_index("ix_trial_ae_nct_id", "trial_ae", ["nct_id"])

  op.create_table(
    "signal_stat",
    sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("drug_id", sa.String(length=64), nullable=False),
    sa.Column("ae_term_id", sa.String(length=64), nullable=False),
    sa.Column("period", sa.String(length=16), nullable=False),
    sa.Column("n11", sa.Integer(), nullable=False),
    sa.Column("n1_", sa.Integer(), nullable=False),
    sa.Column("n_1", sa.Integer(), nullable=False),
    sa.Column("n__", sa.Integer(), nullable=False),
    sa.Column("prr", sa.Float(), nullable=True),
    sa.Column("ror", sa.Float(), nullable=True),
    sa.Column("ror_ci_low", sa.Float(), nullable=True),
    sa.Column("ror_ci_high", sa.Float(), nullable=True),
    sa.Column("ic", sa.Float(), nullable=True),
    sa.Column("ebgm", sa.Float(), nullable=True),
    sa.Column("serious_rate", sa.Float(), nullable=True),
    sa.Column("model_version", sa.String(length=32), nullable=False),
    sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["ae_term_id"], ["ae_term.ae_term_id"]),
    sa.ForeignKeyConstraint(["drug_id"], ["drug.drug_id"]),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("drug_id", "ae_term_id", "period", "model_version", name="uq_signal_stat"),
  )
  op.create_index("ix_signal_stat_drug_id", "signal_stat", ["drug_id"])

  op.create_table(
    "risk_score",
    sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("drug_id", sa.String(length=64), nullable=False),
    sa.Column("ae_term_id", sa.String(length=64), nullable=False),
    sa.Column("n_reports", sa.Integer(), nullable=False),
    sa.Column("prr", sa.Float(), nullable=True),
    sa.Column("ror", sa.Float(), nullable=True),
    sa.Column("omic_risk", sa.Float(), nullable=True),
    sa.Column("dose_risk", sa.Float(), nullable=True),
    sa.Column("serious_rate", sa.Float(), nullable=True),
    sa.Column("fused_score", sa.Float(), nullable=True),
    sa.Column("attr_dose", sa.Float(), nullable=True),
    sa.Column("attr_offtarget", sa.Float(), nullable=True),
    sa.Column("attr_genetic", sa.Float(), nullable=True),
    sa.Column("model_version", sa.String(length=32), nullable=False),
    sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["ae_term_id"], ["ae_term.ae_term_id"]),
    sa.ForeignKeyConstraint(["drug_id"], ["drug.drug_id"]),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("drug_id", "ae_term_id", "model_version", name="uq_risk_score"),
  )
  op.create_index("ix_risk_score_drug_id", "risk_score", ["drug_id"])

  op.create_table(
    "ground_truth_label",
    sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("drug_id", sa.String(length=64), nullable=False),
    sa.Column("ae_term_id", sa.String(length=64), nullable=False),
    sa.Column("label_type", sa.String(length=32), nullable=False),
    sa.Column("source", sa.String(length=128), nullable=False),
    sa.Column("notes", sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(["ae_term_id"], ["ae_term.ae_term_id"]),
    sa.ForeignKeyConstraint(["drug_id"], ["drug.drug_id"]),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("drug_id", "ae_term_id", "label_type", name="uq_gt_label"),
  )


def downgrade() -> None:
  op.drop_table("ground_truth_label")
  op.drop_table("risk_score")
  op.drop_table("signal_stat")
  op.drop_table("trial_ae")
  op.drop_table("pv_drug_event")
  op.drop_table("pathway_target")
  op.drop_table("drug_target")
  op.drop_table("pv_case")
  op.drop_table("ontology_crosswalk")
  op.drop_table("ae_term")
  op.drop_table("variant")
  op.drop_table("pathway")
  op.drop_table("target")
  op.drop_table("drug")
