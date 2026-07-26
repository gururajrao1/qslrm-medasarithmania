"""Cumulative pull job registry smoke tests."""

from __future__ import annotations

from ingest.jobs import create_job, get_job


def test_job_registry_roundtrip():
  jid = create_job()
  job = get_job(jid)
  assert job is not None
  assert job["status"] == "queued"
  assert get_job("missing") is None
