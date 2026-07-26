"""Container entrypoint — serve immediately; optional bootstrap/seed."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "processed" / "qslrm.db"


def _run(module: str, *args: str) -> None:
  cmd = [sys.executable, "-m", module, *args]
  print("+", " ".join(cmd), flush=True)
  subprocess.check_call(cmd, cwd=ROOT)


def needs_pipeline(session: Session) -> bool:
  from qslrm_erd.models import RiskScore

  n = session.scalar(select(func.count()).select_from(RiskScore).where(RiskScore.fused_score.is_not(None)))
  return int(n or 0) == 0


def _seed_pipeline_bg() -> None:
  fixtures = ROOT / "tests" / "fixtures" / "phase1"
  if not fixtures.exists():
    return
  try:
    from qslrm_erd.db import get_engine, reset_engine

    reset_engine()
    with Session(get_engine()) as session:
      if not needs_pipeline(session):
        print("pipeline already populated; skip", flush=True)
        return
    _run("scripts.run_phase1", "--offline-dir", str(fixtures))
    _run("scripts.run_phase2")
    _run("scripts.run_phase3")
    print("background seed pipeline complete", flush=True)
  except Exception as exc:  # noqa: BLE001
    print(f"background seed pipeline failed: {exc}", flush=True)


def main() -> None:
  os.chdir(ROOT)
  bootstrap = os.getenv("QSLRM_BOOTSTRAP", "1") == "1"
  seed_pipeline = os.getenv("QSLRM_SEED_PIPELINE", "1") == "1"
  has_release_db = DB_PATH.exists() and DB_PATH.stat().st_size > 100_000

  if has_release_db:
    print(f"using release sqlite snapshot ({DB_PATH.stat().st_size} bytes)", flush=True)
    # Don't wipe migrated data
    bootstrap = False
    seed_pipeline = False

  if bootstrap:
    _run("scripts.bootstrap_db")
    from qslrm_erd.db import get_engine, reset_engine
    from qslrm_erd.models import Base

    reset_engine()
    Base.metadata.create_all(get_engine())
    _run("scripts.seed_db")

  if seed_pipeline:
    threading.Thread(target=_seed_pipeline_bg, name="seed-pipeline", daemon=True).start()

  host = os.getenv("HOST", "0.0.0.0")
  port = os.getenv("PORT", "8000")
  raise SystemExit(
    subprocess.call(
      [sys.executable, "-m", "uvicorn", "api.main:app", "--host", host, "--port", port],
      cwd=ROOT,
    )
  )


if __name__ == "__main__":
  main()
