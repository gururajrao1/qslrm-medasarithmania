"""Phase 0 + Phase 1 offline integration tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ingest.normalize import ae_term_id_from_pt, to_nm
from ingest.pipeline import run_phase1
from ingest.qc import build_qc_report
from qslrm_erd.db import get_engine, reset_engine
from qslrm_erd.models import Base, DrugTarget, PvDrugEvent, Variant
from scripts.seed_db import seed_all

FIXTURES = Path(__file__).parent / "fixtures" / "phase1"


@pytest.fixture()
def seeded_session(tmp_path, monkeypatch):
  db_path = tmp_path / "qslrm_phase1.db"
  monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
  reset_engine()
  engine = get_engine()
  Base.metadata.create_all(engine)
  with Session(engine) as session:
    seed_all(session)
    yield session
  reset_engine()


def test_phase0_pass_after_seed(seeded_session):
  report = build_qc_report(seeded_session)
  assert report["phase0_pass"] is True
  assert report["counts"]["drug_mvp"] == 27
  assert report["counts"]["ontology_crosswalk"] >= 20


def test_normalize_helpers():
  assert ae_term_id_from_pt("Drug-induced liver injury").startswith("ae_")
  assert to_nm(1.0, "uM") == 1000.0
  assert to_nm(25.0, "nM") == 25.0


def test_phase1_offline_pipeline(seeded_session):
  summary = run_phase1(seeded_session, offline_dir=FIXTURES)
  assert summary["mode"] == "offline"
  assert summary["steps"]["faers"]["events_ins"] >= 10
  assert summary["steps"]["clinvar"]["variants_ins"] >= 1
  assert summary["steps"]["opentargets"]["pathways_ins"] >= 1
  assert summary["steps"]["chembl"]["dt_ins"] + summary["steps"]["chembl"]["dt_upd"] >= 1

  report = build_qc_report(seeded_session)
  assert report["phase0_pass"] is True
  assert report["phase1_pass"] is True
  assert seeded_session.scalar(select(func.count()).select_from(PvDrugEvent)) >= 10
  assert seeded_session.scalar(select(func.count()).select_from(Variant)) >= 3
  assert seeded_session.scalar(select(func.count()).select_from(DrugTarget)) >= 10
