"""openFDA FAERS ingest — kinase-class slice only (never full dump)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ingest.http_util import get_json
from ingest.normalize import ae_term_id_from_pt, slug
from qslrm_erd.settings import get_settings

OPENFDA_DRUG_EVENT = "https://api.fda.gov/drug/event.json"


def _as_text(value: Any, *, fallback: str | None = None) -> str | None:
  """Coerce openFDA fields that sometimes arrive as dict/list into plain text."""
  if value is None:
    return fallback
  if isinstance(value, str):
    text = value.strip()
    return text or fallback
  if isinstance(value, dict):
    for key in (
      "narrativeincludeclinical",
      "narrativeinclude",
      "text",
      "value",
      "summary",
    ):
      if value.get(key):
        return _as_text(value.get(key), fallback=fallback)
    parts = [str(v).strip() for v in value.values() if isinstance(v, (str, int, float)) and str(v).strip()]
    return "; ".join(parts) if parts else fallback
  if isinstance(value, (list, tuple)):
    parts = [_as_text(v) for v in value]
    parts = [p for p in parts if p]
    return "; ".join(parts) if parts else fallback
  return str(value)


def faers_filter_note() -> str:
  return (
    "MVP rule: filter FAERS to preferred_name IN kinase seed list. "
    "Do not download or ingest the full quarterly dump in Phase 1."
  )


def openfda_search_url(drug_name: str, limit: int = 100, skip: int = 0) -> str:
  q = f'patient.drug.medicinalproduct:"{drug_name}"'
  return f"{OPENFDA_DRUG_EVENT}?search={q}&limit={limit}&skip={skip}"


def fetch_faers_page(drug_name: str, *, limit: int, skip: int) -> dict[str, Any]:
  q = f'patient.drug.medicinalproduct:"{drug_name}"'
  return get_json(OPENFDA_DRUG_EVENT, params={"search": q, "limit": limit, "skip": skip})


def fetch_faers_for_drug(drug_name: str, *, max_results: int | None = None) -> list[dict]:
  settings = get_settings()
  max_n = max_results or settings.faers_max_per_drug
  page = settings.faers_page_size
  results: list[dict] = []
  skip = 0
  while len(results) < max_n:
    batch = min(page, max_n - len(results))
    try:
      data = fetch_faers_page(drug_name, limit=batch, skip=skip)
    except Exception:  # noqa: BLE001 — openFDA may 404 when skip exceeds total
      break
    results_chunk = data.get("results") or []
    if not results_chunk:
      break
    results.extend(results_chunk)
    skip += len(results_chunk)
    meta_total = ((data.get("meta") or {}).get("results") or {}).get("total")
    if meta_total is not None and skip >= int(meta_total):
      break
    if len(results_chunk) < batch:
      break
  return results[:max_n]


def _parse_report_date(raw: str | None):
  if not raw:
    return None
  raw = str(raw).strip()
  if len(raw) >= 8 and raw[:8].isdigit():
    try:
      return datetime.strptime(raw[:8], "%Y%m%d").date()
    except ValueError:
      pass
  for fmt in ("%Y-%m-%d", "%Y%m"):
    try:
      return datetime.strptime(raw, fmt).date()
    except ValueError:
      continue
  return None


def _drug_role(drug_obj: dict) -> str | None:
  char = (drug_obj.get("drugcharacterization") or "").strip()
  # 1=Suspect, 2=Concomitant, 3=Interacting
  return {"1": "PS", "2": "C", "3": "I"}.get(char, char or None)


def build_faers_rows(
  *,
  drug_id: str,
  drug_name: str,
  events: list[dict],
  source_period: str = "openfda_live",
) -> tuple[list[dict], list[dict], list[dict]]:
  """Return (ae_terms, pv_cases, pv_drug_events)."""
  ae_terms: dict[str, dict] = {}
  cases: dict[str, dict] = {}
  links: list[dict] = []

  for ev in events:
    safety_id = str(ev.get("safetyreportid") or ev.get("companynumb") or "")
    if not safety_id:
      continue
    case_id = f"faers_{safety_id}"
    patient = ev.get("patient") or {}
    serious_flag = str(ev.get("serious") or "") in {"1", "Yes", "yes"}
    sex_raw = str(patient.get("patientsex") or ev.get("patientsex") or "").strip()
    sex = {"1": "male", "2": "female", "male": "male", "female": "female"}.get(sex_raw.lower(), sex_raw or None)
    age_group = _as_text(patient.get("patientagegroup") or ev.get("patientagegroup"))
    if not age_group and patient.get("patientonsetage"):
      try:
        age = float(patient.get("patientonsetage"))
        age_group = "65+" if age >= 65 else ("45-64" if age >= 45 else "18-44")
      except (TypeError, ValueError):
        age_group = None
    narrative = _as_text(
      ev.get("narrative")
      or patient.get("summary")
      or patient.get("patientnarrative")
      or ev.get("reportnarrative"),
      fallback=f"Patient experienced adverse events while on {drug_name}.",
    )
    period = _as_text(ev.get("source_period") or source_period) or source_period
    country = _as_text(ev.get("occurcountry") or ev.get("primarysourcecountry"))
    # Map country → PV region for global filters (US / EU / Global)
    eu = {"DE", "FR", "GB", "IT", "ES", "NL", "SE", "BE", "AT", "PL", "IE", "DK", "FI", "PT"}
    if country in {"US", "USA"}:
      region = "US"
    elif country in eu:
      region = "EU"
    else:
      region = "Global"
    cases[case_id] = {
      "case_id": case_id,
      "report_date": _parse_report_date(ev.get("receiptdate") or ev.get("receivedate")),
      "country": country,
      "source_region": _as_text(ev.get("source_region")) or region,
      "sex": sex,
      "age_group": age_group,
      "serious": serious_flag,
      "outcome": None,
      "source_period": period,
      "narrative": narrative,
    }

    # Prefer matching medicinalproduct to our drug; else take first suspect drug row
    drug_rows = patient.get("drug") or []
    matched = None
    for d in drug_rows:
      med = (d.get("medicinalproduct") or "").lower()
      if drug_name.lower() in med or med in drug_name.lower():
        matched = d
        break
    if matched is None:
      for d in drug_rows:
        if str(d.get("drugcharacterization")) == "1":
          matched = d
          break
    if matched is None and drug_rows:
      matched = drug_rows[0]

    dose_text = None
    dose_proxy = None
    if matched:
      dose_text = _as_text(matched.get("drugdosagetext") or matched.get("drugdosageform"))
      role = _drug_role(matched)
    else:
      role = "PS"

    for rxn in patient.get("reaction") or []:
      pt = (rxn.get("reactionmeddrapt") or "").strip()
      if not pt:
        continue
      ae_id = ae_term_id_from_pt(pt)
      ae_terms[ae_id] = {
        "ae_term_id": ae_id,
        "pt_string": pt,
        "meddra_pt_code": _as_text(rxn.get("reactionmeddraptcode") or rxn.get("reactionmeddrapt_code")),
        "soc": None,
        "snomed_id": None,
        "hpo_id": None,
        "source": "openfda_pt",
      }
      outcome = rxn.get("reactionoutcome")
      if outcome is not None and cases[case_id]["outcome"] is None:
        cases[case_id]["outcome"] = _as_text(outcome)
      links.append(
        {
          "case_id": case_id,
          "drug_id": drug_id,
          "ae_term_id": ae_id,
          "pt_string": pt,
          "drug_role": role,
          "dose_text": (dose_text[:256] if dose_text else None),
          "dose_proxy": dose_proxy,
        }
      )

  return list(ae_terms.values()), list(cases.values()), links


def snapshot_raw(drug_name: str, events: list[dict], raw_dir: str | Path) -> Path:
  path = Path(raw_dir) / "faers" / f"{slug(drug_name)}.json"
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(json.dumps(events, indent=2), encoding="utf-8")
  return path
