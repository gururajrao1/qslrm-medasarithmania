"""HTTP helpers with retries for public APIs."""

from __future__ import annotations

import time
from typing import Any

import httpx

from qslrm_erd.settings import get_settings


class HttpError(RuntimeError):
  pass


def get_json(
  url: str,
  *,
  params: dict[str, Any] | None = None,
  headers: dict[str, str] | None = None,
) -> Any:
  settings = get_settings()
  last_err: Exception | None = None
  for attempt in range(1, settings.http_max_retries + 1):
    try:
      with httpx.Client(timeout=settings.http_timeout_s, follow_redirects=True) as client:
        resp = client.get(url, params=params, headers=headers)
        if resp.status_code == 429:
          time.sleep(min(2**attempt, 30))
          continue
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # noqa: BLE001 — retry then raise
      last_err = exc
      time.sleep(min(1.5 * attempt, 10))
  raise HttpError(f"GET failed after retries: {url} ({last_err})")


def post_json(
  url: str,
  payload: dict[str, Any],
  *,
  headers: dict[str, str] | None = None,
) -> Any:
  settings = get_settings()
  last_err: Exception | None = None
  hdrs = {"Content-Type": "application/json", **(headers or {})}
  for attempt in range(1, settings.http_max_retries + 1):
    try:
      with httpx.Client(timeout=settings.http_timeout_s, follow_redirects=True) as client:
        resp = client.post(url, json=payload, headers=hdrs)
        if resp.status_code == 429:
          time.sleep(min(2**attempt, 30))
          continue
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # noqa: BLE001
      last_err = exc
      time.sleep(min(1.5 * attempt, 10))
  raise HttpError(f"POST failed after retries: {url} ({last_err})")
