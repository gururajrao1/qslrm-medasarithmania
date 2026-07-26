"""Append-only event ledger + WebSocket broadcast hub (streaming MVP)."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from qslrm_erd.models import EventLedger

# Connected WebSocket send callables (set by api.main)
_subscribers: set[Any] = set()
_loop: asyncio.AbstractEventLoop | None = None


def set_event_loop(loop: asyncio.AbstractEventLoop | None) -> None:
  global _loop
  _loop = loop


def register_subscriber(ws: Any) -> None:
  _subscribers.add(ws)


def unregister_subscriber(ws: Any) -> None:
  _subscribers.discard(ws)


def payload_sha256(payload: dict[str, Any] | list | str) -> str:
  if isinstance(payload, str):
    raw = payload.encode("utf-8")
  else:
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
  return hashlib.sha256(raw).hexdigest()


def append_event(
  session: Session,
  *,
  source: str,
  entity_key: str,
  payload: dict[str, Any] | list | str,
  event_type: str = "ingest",
  drug_id: str | None = None,
  ae_term_id: str | None = None,
  summary: str | None = None,
  broadcast: bool = True,
) -> EventLedger | None:
  """Idempotent append. Returns row if inserted, None if duplicate hash."""
  if isinstance(payload, str):
    payload_json = payload
    digest = payload_sha256(payload)
  else:
    payload_json = json.dumps(payload, default=str)
    digest = payload_sha256(payload)

  existing = session.scalar(
    select(EventLedger).where(
      EventLedger.source == source,
      EventLedger.entity_key == entity_key,
      EventLedger.payload_sha256 == digest,
    )
  )
  if existing is not None:
    return None

  row = EventLedger(
    source=source,
    entity_key=entity_key[:256],
    drug_id=drug_id,
    ae_term_id=ae_term_id,
    event_type=event_type,
    payload_json=payload_json,
    payload_sha256=digest,
    summary=(summary or "")[:512] or None,
  )
  session.add(row)
  session.flush()

  if broadcast:
    patch = ledger_to_patch(row)
    schedule_broadcast(patch)
  return row


def ledger_to_patch(row: EventLedger) -> dict[str, Any]:
  return {
    "type": "ledger_event",
    "event_id": row.id,
    "source": row.source,
    "event_type": row.event_type,
    "entity_key": row.entity_key,
    "drug_id": row.drug_id,
    "ae_term_id": row.ae_term_id,
    "summary": row.summary,
    "payload_sha256": row.payload_sha256,
    "ts": (row.created_at or datetime.now(timezone.utc)).isoformat(),
  }


def schedule_broadcast(message: dict[str, Any]) -> None:
  """Thread-safe: schedule coroutine on the FastAPI event loop if available."""
  loop = _loop
  if loop is None or not loop.is_running():
    return
  try:
    asyncio.run_coroutine_threadsafe(broadcast(message), loop)
  except Exception:  # noqa: BLE001
    pass


async def broadcast(message: dict[str, Any]) -> None:
  dead = []
  text = json.dumps(message, default=str)
  for ws in list(_subscribers):
    try:
      await ws.send_text(text)
    except Exception:  # noqa: BLE001
      dead.append(ws)
  for ws in dead:
    _subscribers.discard(ws)


def recent_events(session: Session, *, limit: int = 50, after_id: int = 0) -> list[EventLedger]:
  q = select(EventLedger).order_by(EventLedger.id.desc()).limit(limit)
  if after_id:
    q = select(EventLedger).where(EventLedger.id > after_id).order_by(EventLedger.id.asc()).limit(limit)
  rows = list(session.scalars(q).all())
  if not after_id:
    rows.reverse()
  return rows
