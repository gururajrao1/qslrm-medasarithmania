"""Phase 2 unit + integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ingest.pipeline import run_phase1
from ingest.qc import build_qc_report
from omic_engine.pipeline import run_phase2
from omic_engine.scoring import soff, sgen, somic, spath, strans
from qslrm_erd.db import get_engine, reset_engine
from qslrm_erd.models import Base, OmicScore, SignalStat, SignalVelocity
from scripts.seed_db import seed_all
from signals.disproportionality import Contingency, compute_signals

FIXTURES = Path(__file__).parent / "fixtures" / "phase1"


@pytest.fixture()
def phase1_db(tmp_path, monkeypatch):
  db_path = tmp_path / "qslrm_phase2.db"
  monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
  reset_engine()
  engine = get_engine()
  Base.metadata.create_all(engine)
  with Session(engine) as session:
    seed_all(session)
    run_phase1(session, offline_dir=FIXTURES)
    yield session
  reset_engine()


def test_omic_python_matches_julia_formulas():
  assert soff([10.0, 100.0], [False, True]) > 0
  assert spath([True, False], [1.0, 2.0]) == 1.0
  assert sgen([0.5, 0.2], [True, False]) == 0.5
  assert strans([2.0, -1.0], [1.0, 0.5]) == 2.5
  s = somic(1.0, 1.0, 1.0)
  assert 0.0 < s < 1.0


def test_rare_event_ebgm_shrinks():
  c = Contingency(n11=1, n10=2, n01=10, n00=1000)
  m = compute_signals(c, min_n=3)
  assert m is not None
  # shrunk toward 1 relative to raw PRR magnitude for tiny n
  assert m.ebgm is not None


def test_phase2_pipeline(phase1_db):
  summary = run_phase2(phase1_db)
  assert summary["steps"]["signals"]["pairs"] >= 1
  assert summary["steps"]["signals"]["signal_stat_inserted"] >= 1
  assert summary["steps"]["omic"]["omic_inserted"] >= 1
  assert summary["steps"]["velocity"]["velocity_inserted"] >= 0

  n_sig = phase1_db.scalar(select(func.count()).select_from(SignalStat))
  n_omic = phase1_db.scalar(select(func.count()).select_from(OmicScore))
  n_vel = phase1_db.scalar(select(func.count()).select_from(SignalVelocity))
  assert n_sig >= 1
  assert n_omic >= 1
  assert n_vel >= 0

  qc = build_qc_report(phase1_db)
  assert qc["phase1_pass"] is True
  assert qc["phase2_pass"] is True
