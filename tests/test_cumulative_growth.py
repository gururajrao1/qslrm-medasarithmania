"""Cumulative pull must grow fused pairs even when live FAERS returns duplicates."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "processed" / "qslrm.db"


@pytest.mark.skipif(not SRC.exists(), reason="local qslrm.db missing")
def test_cumulative_growth_increases_fused(tmp_path, monkeypatch):
  import shutil

  db = tmp_path / "t.db"
  shutil.copy2(SRC, db)
  monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db.as_posix()}")

  from qslrm_erd.db import get_engine, reset_engine
  from qslrm_erd.models import RiskScore
  from qslrm_erd.settings import get_settings
  from ingest.cumulative import run_cumulative_pull

  get_settings.cache_clear()
  reset_engine()

  with Session(get_engine()) as session:
    before = int(
      session.scalar(select(func.count()).select_from(RiskScore).where(RiskScore.fused_score.is_not(None)))
      or 0
    )
    summary = run_cumulative_pull(session, live=False, faers_limit=5, recompute=True)
    after = int(
      session.scalar(select(func.count()).select_from(RiskScore).where(RiskScore.fused_score.is_not(None)))
      or 0
    )

  assert summary["delta"]["fused_pairs"] > 0
  assert summary["delta"]["pv_events"] > 0
  assert after > before
  assert after == summary["after"]["fused_pairs"]
