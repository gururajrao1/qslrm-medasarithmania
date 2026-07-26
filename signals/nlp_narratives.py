"""Rule-based clinical NLP on FAERS narratives (BioClinicalBERT upgrade path)."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from qslrm_erd.models import NarrativeEntity, PvCase, PvDrugEvent

SYMPTOM_PATTERNS = [
  (r"\bnause\w*", "symptom", "nausea"),
  (r"\brash\b", "symptom", "rash"),
  (r"\bhepatotox\w*|\bliver\s+injury\b|\belevated\s+ALT\b", "symptom", "hepatotoxicity"),
  (r"\bQT\s*prolong\w*", "symptom", "qt_prolongation"),
  (r"\binterstitial\s+lung\b|\bpneumonitis\b", "symptom", "ild"),
  (r"\bdiarrh?oe?a\b", "symptom", "diarrhoea"),
]
DOSE_PAT = re.compile(r"(\d+\s?mg(?:\s*/\s*day)?)", re.I)
OFFLABEL_PAT = re.compile(r"off[-\s]?label", re.I)
TIMING_PAT = re.compile(r"(after\s+\d+\s+(?:day|week|month)s?|on\s+day\s+\d+)", re.I)


def extract_entities(narrative: str) -> list[dict]:
  text = narrative or ""
  found: list[dict] = []
  for pat, etype, label in SYMPTOM_PATTERNS:
    if re.search(pat, text, flags=re.I):
      found.append({"entity_type": etype, "entity_text": label, "confidence": 0.75})
  for m in DOSE_PAT.finditer(text):
    found.append({"entity_type": "dose", "entity_text": m.group(1), "confidence": 0.85})
  if OFFLABEL_PAT.search(text):
    found.append({"entity_type": "offlabel", "entity_text": "off-label use", "confidence": 0.8})
  for m in TIMING_PAT.finditer(text):
    found.append({"entity_type": "timing", "entity_text": m.group(1), "confidence": 0.7})
  return found


def run_narrative_nlp(session: Session) -> dict:
  cases = session.scalars(select(PvCase).where(PvCase.narrative.is_not(None))).all()
  # map case -> primary drug if available
  case_drug = {
    r.case_id: r.drug_id
    for r in session.scalars(select(PvDrugEvent)).all()
  }
  inserted = 0
  for case in cases:
    # clear prior extractions for idempotency
    for old in session.scalars(
      select(NarrativeEntity).where(NarrativeEntity.case_id == case.case_id)
    ).all():
      session.delete(old)
    for ent in extract_entities(case.narrative or ""):
      session.add(
        NarrativeEntity(
          case_id=case.case_id,
          drug_id=case_drug.get(case.case_id),
          entity_type=ent["entity_type"],
          entity_text=ent["entity_text"],
          confidence=ent["confidence"],
          extractor="rule_nlp",
        )
      )
      inserted += 1
  session.commit()
  return {"narrative_entities": inserted, "cases": len(cases)}
