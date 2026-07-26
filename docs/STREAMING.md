# Streaming ingestion (Phase 5 MVP)

Append-only **event ledger** + **WebSocket** live patches. Production CDC (Debezium / Postgres logical decoding) is documented in [MASTER_SYSTEM_PROMPT.md](MASTER_SYSTEM_PROMPT.md); this MVP works on SQLite.

## Flow

1. Ingest workers call `stream.ledger.append_event(...)` with source, entity keys, and raw JSON.
2. Rows land in `event_ledger` with `payload_sha256` (dedupe-friendly content hash).
3. Connected clients on `WS /v1/stream` receive `{type, event_id, source, drug_id, ae_term_id, ts, summary}`.
4. Optional: `POST /v1/stream/ingest-tick` appends a demo tick and broadcasts (UI refresh hook).

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| WS | `/v1/stream` | Subscribe to live patches + heartbeat |
| GET | `/v1/stream/events?limit=` | Recent ledger rows (REST replay) |
| POST | `/v1/stream/ingest-tick` | Append synthetic ledger event + broadcast |

## Dedup

Same `(source, entity_key, payload_sha256)` is not inserted twice (idempotent append).
