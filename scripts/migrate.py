"""Run Alembic migrations to head."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
  root = Path(__file__).resolve().parents[1]
  cmd = [sys.executable, "-m", "alembic", "upgrade", "head"]
  raise SystemExit(subprocess.call(cmd, cwd=root))


if __name__ == "__main__":
  main()
