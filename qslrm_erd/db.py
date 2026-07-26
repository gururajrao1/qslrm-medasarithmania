"""SQLAlchemy engine / session helpers."""

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from qslrm_erd.settings import get_settings
from qslrm_erd.urlutil import normalize_database_url

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def reset_engine() -> None:
  global _engine, _SessionLocal
  if _engine is not None:
    _engine.dispose()
  _engine = None
  _SessionLocal = None
  get_settings.cache_clear()


def get_engine() -> Engine:
  global _engine, _SessionLocal
  if _engine is None:
    settings = get_settings()
    url = normalize_database_url(settings.database_url)
    connect_args = {}
    if url.startswith("sqlite"):
      connect_args["check_same_thread"] = False
    _engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)

    if url.startswith("sqlite"):

      @event.listens_for(_engine, "connect")
      def _fk_on(dbapi_conn, _):  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
  return _engine


def get_session() -> Iterator[Session]:
  get_engine()
  assert _SessionLocal is not None
  session = _SessionLocal()
  try:
    yield session
    session.commit()
  except Exception:
    session.rollback()
    raise
  finally:
    session.close()
