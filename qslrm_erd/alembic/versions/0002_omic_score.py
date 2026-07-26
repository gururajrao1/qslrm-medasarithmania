"""0002 — omic_score table for Phase 2 multi-omic components.

Revision ID: 0002_omic_score
Revises: 0001_initial_qslrm_erd
Create Date: 2026-07-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_omic_score"
down_revision: str | None = "0001_initial_qslrm_erd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
  op.create_table(
    "omic_score",
    sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("drug_id", sa.String(length=64), nullable=False),
    sa.Column("ae_term_id", sa.String(length=64), nullable=False),
    sa.Column("s_off", sa.Float(), nullable=False),
    sa.Column("s_path", sa.Float(), nullable=False),
    sa.Column("s_gen", sa.Float(), nullable=False),
    sa.Column("omic_risk", sa.Float(), nullable=False),
    sa.Column("engine", sa.String(length=32), nullable=False),
    sa.Column("model_version", sa.String(length=32), nullable=False),
    sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["ae_term_id"], ["ae_term.ae_term_id"]),
    sa.ForeignKeyConstraint(["drug_id"], ["drug.drug_id"]),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("drug_id", "ae_term_id", "model_version", name="uq_omic_score"),
  )
  op.create_index("ix_omic_score_drug_id", "omic_score", ["drug_id"])


def downgrade() -> None:
  op.drop_table("omic_score")
