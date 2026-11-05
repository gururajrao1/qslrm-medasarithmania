# QSLRM local run (Windows PowerShell). Run from the repo root.
$ErrorActionPreference = "Stop"
if (-not (Test-Path .\pyproject.toml -PathType Leaf)) {
  throw "Run .\run_local.ps1 from the repo root (pyproject.toml not found here)."
}
if (-not $env:PORT) { $env:PORT = "8000" }
if (-not (Test-Path .\.venv)) { python -m venv .venv }
.\.venv\Scripts\python -m pip install -e ".[dev]"
if (-not (Test-Path .\.env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python -m scripts.bootstrap_db
.\.venv\Scripts\python -m scripts.seed_db
.\.venv\Scripts\python -m scripts.run_phase1 --offline-dir tests/fixtures/phase1
.\.venv\Scripts\python -m scripts.run_phase2
.\.venv\Scripts\python -m scripts.run_phase3
.\.venv\Scripts\python -m uvicorn api.main:app --host 127.0.0.1 --port $env:PORT
