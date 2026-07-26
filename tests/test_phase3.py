"""Phase 3 fusion integration test."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fusion.pipeline import run_phase3
from ingest.pipeline import run_phase1
from ingest.qc import build_qc_report
from omic_engine.pipeline import run_phase2
from qslrm_erd.db import get_engine, reset_engine
from qslrm_erd.models import Base, RiskScore
from scripts.seed_db import seed_all

FIXTURES = Path(__file__).parent / "fixtures" / "phase1"


@pytest.fixture()
def phase2_db(tmp_path, monkeypatch):
  db_path = tmp_path / "qslrm_phase3.db"
  monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
  reset_engine()
  engine = get_engine()
  Base.metadata.create_all(engine)
  with Session(engine) as session:
    seed_all(session)
    run_phase1(session, offline_dir=FIXTURES)
    run_phase2(session)
    yield session
  reset_engine()


def test_phase3_fusion_and_attribution(phase2_db):
  summary = run_phase3(phase2_db)
  assert summary["steps"]["fusion"]["fused"] >= 1

  n_fused = phase2_db.scalar(
    select(func.count()).select_from(RiskScore).where(RiskScore.fused_score.is_not(None))
  )
  assert n_fused >= 1

  row = phase2_db.scalars(
    select(RiskScore).where(RiskScore.fused_score.is_not(None)).limit(1)
  ).first()
  assert row is not None
  assert row.attr_dose is not None
  assert row.attr_transcriptomic is not None
  total = row.attr_dose + row.attr_offtarget + row.attr_transcriptomic + row.attr_genetic
  assert abs(total - 1.0) < 1e-5

  qc = build_qc_report(phase2_db)
  assert qc["phase2_pass"] is True
  assert qc["phase3_pass"] is True


def test_fuse_splits_genetic_when_s_gen_present():
  from fusion import fuse_risk

  r = fuse_risk(signal_z=1.0, omic_z=1.0, dose_z=0.2, s_off=1.0, s_trans=0.1, s_gen=3.0)
  assert r.attr_genetic > r.attr_offtarget
  assert abs(
    r.attr_dose + r.attr_offtarget + r.attr_transcriptomic + r.attr_genetic - 1.0
  ) < 1e-6
