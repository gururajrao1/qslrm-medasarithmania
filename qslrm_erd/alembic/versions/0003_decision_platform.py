"""0003 — decision platform + CT/PV module tables.

Revision ID: 0003_decision_platform
Revises: 0002_omic_score
Create Date: 2026-07-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_decision_platform"
down_revision: str | None = "0002_omic_score"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
  op.add_column("drug", sa.Column("cyp_substrates", sa.String(length=256), nullable=True))
  op.add_column("variant", sa.Column("pharmgkb_id", sa.String(length=64), nullable=True))
  op.add_column("variant", sa.Column("metabolizer_impact", sa.String(length=64), nullable=True))

  op.add_column("pv_case", sa.Column("sex", sa.String(length=16), nullable=True))
  op.add_column("pv_case", sa.Column("age_group", sa.String(length=32), nullable=True))
  op.add_column("pv_case", sa.Column("narrative", sa.Text(), nullable=True))

  op.add_column("trial_ae", sa.Column("phase", sa.String(length=16), nullable=True))
  op.add_column("trial_ae", sa.Column("median_onset_weeks", sa.Float(), nullable=True))

  op.add_column("omic_score", sa.Column("s_trans", sa.Float(), nullable=False, server_default="0"))
  op.add_column("risk_score", sa.Column("attr_transcriptomic", sa.Float(), nullable=True))
  op.add_column(
    "risk_score",
    sa.Column("action_needed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
  )
  op.add_column("risk_score", sa.Column("action_flag", sa.String(length=64), nullable=True))
  op.add_column(
    "risk_score",
    sa.Column("rising_signal", sa.Boolean(), nullable=False, server_default=sa.text("false")),
  )

  op.create_table(
    "transcript_signature",
    sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("drug_id", sa.String(length=64), nullable=False),
    sa.Column("gene_symbol", sa.String(length=64), nullable=False),
    sa.Column("z_score", sa.Float(), nullable=False),
    sa.Column("tox_weight", sa.Float(), nullable=False),
    sa.Column("direction", sa.String(length=16), nullable=True),
    sa.Column("source", sa.String(length=64), nullable=False),
    sa.ForeignKeyConstraint(["drug_id"], ["drug.drug_id"]),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("drug_id", "gene_symbol", "source", name="uq_transcript_sig"),
  )
  op.create_index("ix_transcript_signature_drug_id", "transcript_signature", ["drug_id"])
  op.create_index("ix_transcript_signature_gene_symbol", "transcript_signature", ["gene_symbol"])

  op.create_table(
    "narrative_entity",
    sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("case_id", sa.String(length=64), nullable=False),
    sa.Column("drug_id", sa.String(length=64), nullable=True),
    sa.Column("entity_type", sa.String(length=64), nullable=False),
    sa.Column("entity_text", sa.String(length=256), nullable=False),
    sa.Column("confidence", sa.Float(), nullable=False),
    sa.Column("extractor", sa.String(length=64), nullable=False),
    sa.ForeignKeyConstraint(["case_id"], ["pv_case.case_id"]),
    sa.ForeignKeyConstraint(["drug_id"], ["drug.drug_id"]),
    sa.PrimaryKeyConstraint("id"),
  )
  op.create_index("ix_narrative_case", "narrative_entity", ["case_id"])

  op.create_table(
    "trial_onset_curve",
    sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("drug_id", sa.String(length=64), nullable=False),
    sa.Column("ae_term_id", sa.String(length=64), nullable=False),
    sa.Column("nct_id", sa.String(length=32), nullable=False),
    sa.Column("week", sa.Float(), nullable=False),
    sa.Column("survival_prob", sa.Float(), nullable=False),
    sa.Column("event_prob", sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(["ae_term_id"], ["ae_term.ae_term_id"]),
    sa.ForeignKeyConstraint(["drug_id"], ["drug.drug_id"]),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("drug_id", "ae_term_id", "week", "nct_id", name="uq_onset_curve"),
  )
  op.create_index("ix_trial_onset_curve_drug_id", "trial_onset_curve", ["drug_id"])

  op.create_table(
    "trial_concomitant",
    sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("nct_id", sa.String(length=32), nullable=False),
    sa.Column("drug_id", sa.String(length=64), nullable=False),
    sa.Column("concomitant_name", sa.String(length=128), nullable=False),
    sa.Column("concomitant_rxnorm", sa.String(length=32), nullable=True),
    sa.Column("cyp_enzymes", sa.String(length=128), nullable=True),
    sa.ForeignKeyConstraint(["drug_id"], ["drug.drug_id"]),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("nct_id", "drug_id", "concomitant_name", name="uq_trial_comed"),
  )
  op.create_index("ix_trial_concomitant_nct_id", "trial_concomitant", ["nct_id"])

  op.create_table(
    "ddi_risk",
    sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("drug_id", sa.String(length=64), nullable=False),
    sa.Column("concomitant_name", sa.String(length=128), nullable=False),
    sa.Column("enzyme", sa.String(length=32), nullable=False),
    sa.Column("risk_level", sa.String(length=16), nullable=False),
    sa.Column("mechanism", sa.String(length=128), nullable=False),
    sa.Column("notes", sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(["drug_id"], ["drug.drug_id"]),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("drug_id", "concomitant_name", "enzyme", name="uq_ddi_risk"),
  )
  op.create_index("ix_ddi_risk_drug_id", "ddi_risk", ["drug_id"])

  op.create_table(
    "signal_velocity",
    sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("drug_id", sa.String(length=64), nullable=False),
    sa.Column("ae_term_id", sa.String(length=64), nullable=False),
    sa.Column("period_from", sa.String(length=16), nullable=False),
    sa.Column("period_to", sa.String(length=16), nullable=False),
    sa.Column("ror_from", sa.Float(), nullable=False),
    sa.Column("ror_to", sa.Float(), nullable=False),
    sa.Column("delta_ror", sa.Float(), nullable=False),
    sa.Column("velocity", sa.Float(), nullable=False),
    sa.Column("rising", sa.Boolean(), nullable=False),
    sa.Column("model_version", sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(["ae_term_id"], ["ae_term.ae_term_id"]),
    sa.ForeignKeyConstraint(["drug_id"], ["drug.drug_id"]),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint(
      "drug_id", "ae_term_id", "period_from", "period_to", "model_version", name="uq_velocity"
    ),
  )
  op.create_index("ix_signal_velocity_drug_id", "signal_velocity", ["drug_id"])

  op.create_table(
    "demographic_signal",
    sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("drug_id", sa.String(length=64), nullable=False),
    sa.Column("ae_term_id", sa.String(length=64), nullable=False),
    sa.Column("stratum_type", sa.String(length=32), nullable=False),
    sa.Column("stratum_value", sa.String(length=64), nullable=False),
    sa.Column("n_reports", sa.Integer(), nullable=False),
    sa.Column("share", sa.Float(), nullable=False),
    sa.Column("lift_vs_background", sa.Float(), nullable=True),
    sa.Column("model_version", sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(["ae_term_id"], ["ae_term.ae_term_id"]),
    sa.ForeignKeyConstraint(["drug_id"], ["drug.drug_id"]),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint(
      "drug_id", "ae_term_id", "stratum_type", "stratum_value", "model_version", name="uq_demo_sig"
    ),
  )
  op.create_index("ix_demographic_signal_drug_id", "demographic_signal", ["drug_id"])

  op.create_table(
    "protocol_exclusion",
    sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("drug_id", sa.String(length=64), nullable=False),
    sa.Column("ae_term_id", sa.String(length=64), nullable=False),
    sa.Column("variant_id", sa.String(length=64), nullable=True),
    sa.Column("clause_text", sa.Text(), nullable=False),
    sa.Column("rationale", sa.Text(), nullable=False),
    sa.Column("estimated_adr_reduction", sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(["ae_term_id"], ["ae_term.ae_term_id"]),
    sa.ForeignKeyConstraint(["drug_id"], ["drug.drug_id"]),
    sa.ForeignKeyConstraint(["variant_id"], ["variant.variant_id"]),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("drug_id", "ae_term_id", "variant_id", name="uq_protocol_excl"),
  )


def downgrade() -> None:
  op.drop_table("protocol_exclusion")
  op.drop_table("demographic_signal")
  op.drop_table("signal_velocity")
  op.drop_table("ddi_risk")
  op.drop_table("trial_concomitant")
  op.drop_table("trial_onset_curve")
  op.drop_table("narrative_entity")
  op.drop_table("transcript_signature")
  op.drop_column("risk_score", "rising_signal")
  op.drop_column("risk_score", "action_flag")
  op.drop_column("risk_score", "action_needed")
  op.drop_column("risk_score", "attr_transcriptomic")
  op.drop_column("omic_score", "s_trans")
  op.drop_column("trial_ae", "median_onset_weeks")
  op.drop_column("trial_ae", "phase")
  op.drop_column("pv_case", "narrative")
  op.drop_column("pv_case", "age_group")
  op.drop_column("pv_case", "sex")
  op.drop_column("variant", "metabolizer_impact")
  op.drop_column("variant", "pharmgkb_id")
  op.drop_column("drug", "cyp_substrates")
