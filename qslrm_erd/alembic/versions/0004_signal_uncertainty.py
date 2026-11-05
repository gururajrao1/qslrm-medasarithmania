"""0004 — signal uncertainty columns (chi2/CI/IC025/EB bounds, MH ROR).

Revision ID: 0004_signal_uncertainty
Revises: 0003_decision_platform
Create Date: 2026-11-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_signal_uncertainty"
down_revision: str | None = "0003_decision_platform"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
  op.add_column("signal_stat", sa.Column("prr_chi2", sa.Float(), nullable=True))
  op.add_column("signal_stat", sa.Column("prr_ci_low", sa.Float(), nullable=True))
  op.add_column("signal_stat", sa.Column("prr_ci_high", sa.Float(), nullable=True))
  op.add_column("signal_stat", sa.Column("ic025", sa.Float(), nullable=True))
  op.add_column("signal_stat", sa.Column("eb05", sa.Float(), nullable=True))
  op.add_column("signal_stat", sa.Column("eb95", sa.Float(), nullable=True))
  op.add_column("demographic_signal", sa.Column("mh_ror", sa.Float(), nullable=True))


def downgrade() -> None:
  op.drop_column("demographic_signal", "mh_ror")
  op.drop_column("signal_stat", "eb95")
  op.drop_column("signal_stat", "eb05")
  op.drop_column("signal_stat", "ic025")
  op.drop_column("signal_stat", "prr_ci_high")
  op.drop_column("signal_stat", "prr_ci_low")
  op.drop_column("signal_stat", "prr_chi2")
