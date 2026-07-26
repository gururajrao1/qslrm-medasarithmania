"""Bootstrap database schema (create_all — works for SQLite + Postgres/psycopg3)."""

from __future__ import annotations

import argparse
from pathlib import Path

from qslrm_erd.db import get_engine, reset_engine
from qslrm_erd.models import Base
from qslrm_erd.settings import get_settings
from qslrm_erd.urlutil import normalize_database_url


def bootstrap() -> str:
  reset_engine()
  settings = get_settings()
  url = normalize_database_url(settings.database_url)
  if url.startswith("sqlite") and ":///" in url:
    raw = url.split(":///", 1)[1]
    path = Path(raw)
    if path.parent and str(path.parent) not in {".", ""}:
      path.parent.mkdir(parents=True, exist_ok=True)
  engine = get_engine()
  Base.metadata.create_all(engine)
  return f"schema created via create_all ({url.split('@')[-1] if '@' in url else url})"


def main() -> None:
  parser = argparse.ArgumentParser(description="Bootstrap QSLRM database schema")
  parser.parse_args()
  print(bootstrap())


if __name__ == "__main__":
  main()
