"""Quick unit tests for CT/PV module helpers."""

from __future__ import annotations

from signals.nlp_narratives import extract_entities
from fusion.decisions import build_decisions, protocol_exclusion_clause


def test_narrative_extracts_symptom_and_dose():
  ents = extract_entities("Patient developed rash after 400 mg / day; off-label use noted after 2 weeks.")
  types = {e["entity_type"] for e in ents}
  assert "symptom" in types
  assert "dose" in types
  assert "offlabel" in types


def test_protocol_clause_mentions_gene():
  clause, rationale = protocol_exclusion_clause(
    drug_name="Imatinib",
    pt_string="Hepatotoxicity",
    gene_symbol="CYP2D6",
    metabolizer_impact="CYP2D6_PM",
    estimated_reduction=0.8,
  )
  assert "CYP2D6" in clause
  assert "80%" in rationale


def test_rising_decision_card():
  cards = build_decisions(
    drug_name="Erlotinib",
    pt_string="Rash",
    fused_score=70.0,
    attr_dose=0.1,
    attr_offtarget=0.2,
    attr_transcriptomic=0.2,
    attr_genetic=0.5,
    rising_signal=True,
  )
  kinds = {c.kind for c in cards}
  assert "rising" in kinds
  assert "genetic_filter" in kinds
