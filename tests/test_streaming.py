"""Streaming ledger + SHA-256 idempotency."""

from __future__ import annotations

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from qslrm_erd.models import Base, EventLedger
from stream.ledger import append_event, ledger_to_patch, payload_sha256


def test_payload_sha256_stable():
  a = payload_sha256({"b": 2, "a": 1})
  b = payload_sha256({"a": 1, "b": 2})
  assert a == b
  assert len(a) == 64


def test_append_event_idempotent(tmp_path):
  engine = create_engine(f"sqlite:///{tmp_path / 'ledger.db'}")
  Base.metadata.create_all(engine)
  with Session(engine) as session:
    row1 = append_event(
      session,
      source="openfda_faers",
      entity_key="drug_x|ae_y",
      payload={"n": 1},
      drug_id=None,
      ae_term_id=None,
      summary="test",
      broadcast=False,
    )
    session.commit()
    assert row1 is not None
    row2 = append_event(
      session,
      source="openfda_faers",
      entity_key="drug_x|ae_y",
      payload={"n": 1},
      broadcast=False,
    )
    session.commit()
    assert row2 is None
    n = session.scalar(select(func.count()).select_from(EventLedger))
    assert n == 1
    patch = ledger_to_patch(row1)
    assert patch["type"] == "ledger_event"
    assert patch["source"] == "openfda_faers"
