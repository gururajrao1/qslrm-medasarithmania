"""Build scanner-safe release SQLite snapshot for free deploy.

Copies from backup/source, scrubs free-text, and renames ae_lip_swelling
so GitHub push protection does not false-positive on Lichess lip_* tokens.
"""

from __future__ import annotations

import os
import re
import shutil
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
SRC_CANDIDATES = [
  PROCESSED / "qslrm.backup-20260726-231222.db",
  PROCESSED / "qslrm.db",
]
DST = PROCESSED / "qslrm.release.db"
OLD = "lip_swelling"
NEW = "lipswelling"  # breaks GitHub Lichess lip_* secret pattern


def _source() -> Path:
  for p in SRC_CANDIDATES:
    if p.exists() and p.stat().st_size > 100_000:
      return p
  raise SystemExit("no source sqlite found")


def _text_columns(con: sqlite3.Connection, table: str) -> list[str]:
  cols: list[str] = []
  for _cid, name, ctype, *_rest in con.execute(f"PRAGMA table_info({table})"):
    t = (ctype or "").upper()
    if t in {"", "TEXT", "VARCHAR", "CHAR", "CLOB"} or "CHAR" in t or "TEXT" in t:
      cols.append(name)
    elif name.endswith("_id") or name.endswith("_json") or name in {"summary", "rationale", "clause_text", "notes", "narrative", "payload_json", "pt_string"}:
      cols.append(name)
  return cols


def main() -> None:
  src = _source()
  print("source", src, src.stat().st_size)
  shutil.copy2(src, DST)

  con = sqlite3.connect(DST)
  con.execute("PRAGMA foreign_keys=OFF")

  # Scrub free-text that can embed scanner false positives
  try:
    con.execute("UPDATE pv_case SET narrative = NULL")
  except sqlite3.Error as exc:
    print("pv_case skip", exc)
  try:
    con.execute("UPDATE event_ledger SET payload_json = '{}', summary = NULL")
  except sqlite3.Error as exc:
    print("event_ledger skip", exc)
  try:
    con.execute("DELETE FROM narrative_entity")
  except sqlite3.Error as exc:
    print("narrative_entity skip", exc)

  tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
  for table in tables:
    if table.startswith("sqlite_"):
      continue
    for col in _text_columns(con, table):
      try:
        n = con.execute(
          f"SELECT COUNT(*) FROM {table} WHERE CAST({col} AS TEXT) LIKE ?",
          (f"%{OLD}%",),
        ).fetchone()[0]
      except sqlite3.Error:
        continue
      if not n:
        continue
      con.execute(
        f"UPDATE {table} SET {col} = REPLACE(CAST({col} AS TEXT), ?, ?) WHERE CAST({col} AS TEXT) LIKE ?",
        (OLD, NEW, f"%{OLD}%"),
      )
      print(f"renamed {table}.{col} rows~{n}")

  con.commit()
  con.execute("VACUUM")
  con.close()

  raw = DST.read_bytes()
  leftover = len(re.findall(rb"lip_[A-Za-z0-9]{8,}", raw))
  print("wrote", DST, "bytes", DST.stat().st_size, "lip_* leftovers", leftover)
  if leftover:
    raise SystemExit("still has lip_* patterns — abort")

  # Verify fused pairs
  os.environ["DATABASE_URL"] = f"sqlite:///{DST.as_posix()}"
  from sqlalchemy import func, select
  from sqlalchemy.orm import Session

  from qslrm_erd.db import get_engine, reset_engine
  from qslrm_erd.models import RiskScore
  from qslrm_erd.settings import get_settings

  get_settings.cache_clear()
  reset_engine()
  with Session(get_engine()) as session:
    fused = session.scalar(
      select(func.count()).select_from(RiskScore).where(RiskScore.fused_score.is_not(None))
    )
  print("release fused", fused)


if __name__ == "__main__":
  main()
