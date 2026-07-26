"""SQLite smoke test for qslrm_erd schema + seed upsert."""

from __future__ import annotations

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from qslrm_erd.models import Base, Drug, OntologyCrosswalk
from scripts.seed_db import seed_all


def test_create_all_and_seed_sqlite(tmp_path):
  engine = create_engine(f"sqlite:///{tmp_path / 'qslrm.db'}")
  Base.metadata.create_all(engine)
  with Session(engine) as session:
    counts = seed_all(session)
    assert counts["drug"] >= 8
    n_drugs = session.scalar(select(func.count()).select_from(Drug))
    assert n_drugs == 27
    drugs = session.scalars(select(Drug)).all()
    assert all(d.chembl_id and d.rxnorm_cui for d in drugs)
    n_xwalk = session.scalar(select(func.count()).select_from(OntologyCrosswalk))
    assert n_xwalk is not None and n_xwalk >= 10
