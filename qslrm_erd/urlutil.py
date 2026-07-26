"""SQLAlchemy URL helpers — Railway injects postgresql://; we need psycopg3."""

from __future__ import annotations


def normalize_database_url(url: str) -> str:
  if url.startswith("postgres://"):
    return "postgresql+psycopg://" + url[len("postgres://") :]
  if url.startswith("postgresql://") and "+psycopg" not in url and "+asyncpg" not in url:
    return "postgresql+psycopg://" + url[len("postgresql://") :]
  return url
