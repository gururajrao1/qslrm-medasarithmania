"""In-memory background job registry for cumulative UI pulls."""

from __future__ import annotations

import threading
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from qslrm_erd.db import get_engine

_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def create_job() -> str:
  job_id = uuid.uuid4().hex[:12]
  with _lock:
    _jobs[job_id] = {
      "job_id": job_id,
      "status": "queued",
      "stage": "queued",
      "detail": {},
      "result": None,
      "error": None,
      "created_at": datetime.now(timezone.utc).isoformat(),
      "updated_at": datetime.now(timezone.utc).isoformat(),
    }
  return job_id


def get_job(job_id: str) -> dict[str, Any] | None:
  with _lock:
    job = _jobs.get(job_id)
    return dict(job) if job else None


def _update(job_id: str, **fields: Any) -> None:
  with _lock:
    job = _jobs.get(job_id)
    if not job:
      return
    job.update(fields)
    job["updated_at"] = datetime.now(timezone.utc).isoformat()


def start_cumulative_job(*, live: bool = True, faers_limit: int = 25) -> str:
  job_id = create_job()

  def _run() -> None:
    from ingest.cumulative import run_cumulative_pull
    from stream.ledger import schedule_broadcast

    _update(job_id, status="running", stage="start")

    def progress(stage: str, detail: dict) -> None:
      _update(job_id, stage=stage, detail=detail)
      schedule_broadcast(
        {
          "type": "ingest_progress",
          "job_id": job_id,
          "stage": stage,
          "detail": detail,
        }
      )

    try:
      engine = get_engine()
      with Session(engine) as session:
        result = run_cumulative_pull(
          session,
          live=live,
          faers_limit=faers_limit,
          progress=progress,
          recompute=True,
        )
      _update(job_id, status="done", stage="done", result=result, detail=result.get("delta") or {})
      schedule_broadcast(
        {
          "type": "ingest_complete",
          "job_id": job_id,
          "delta": result.get("delta"),
          "after": result.get("after"),
        }
      )
    except Exception as exc:  # noqa: BLE001
      _update(
        job_id,
        status="error",
        stage="error",
        error=str(exc),
        detail={"traceback": traceback.format_exc()[-1500:]},
      )
      schedule_broadcast({"type": "ingest_error", "job_id": job_id, "error": str(exc)})

  threading.Thread(target=_run, name=f"cum-{job_id}", daemon=True).start()
  return job_id
