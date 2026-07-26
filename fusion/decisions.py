"""Actionable decision cards + protocol exclusion clauses."""

from __future__ import annotations

from dataclasses import dataclass

from qslrm_erd.settings import get_settings


@dataclass(frozen=True)
class DecisionCard:
  kind: str  # dose | genetic_filter | regulatory | rising
  title: str
  body: str
  priority: int


def build_decisions(
  *,
  drug_name: str,
  pt_string: str,
  fused_score: float | None,
  attr_dose: float | None,
  attr_offtarget: float | None,
  attr_transcriptomic: float | None,
  attr_genetic: float | None,
  rising_signal: bool = False,
  metabolizer_impact: str | None = None,
  is_bbw: bool = False,
  literature_confirmed: bool = False,
  label_sources: list[str] | None = None,
) -> list[DecisionCard]:
  settings = get_settings()
  cards: list[DecisionCard] = []
  a_off = attr_offtarget or 0.0
  a_gen = attr_genetic or 0.0
  a_tr = attr_transcriptomic or 0.0
  a_dose = attr_dose or 0.0
  fused = fused_score or 0.0

  if a_off >= max(a_gen, a_tr, a_dose) and a_off >= 0.35:
    drop = min(25, int(round(a_off * 40)))
    cards.append(
      DecisionCard(
        kind="dose",
        title="Dose recommendation",
        body=(
          f"{int(a_off * 100)}% off-target driven for {drug_name} ↔ {pt_string}. "
          f"Consider reducing dose by ~{drop}% to lower toxicity while preserving on-target efficacy. "
          "Validate against exposure–response before protocol change."
        ),
        priority=1,
      )
    )

  if a_gen >= 0.25 or (metabolizer_impact and "PM" in metabolizer_impact.upper()):
    gene = metabolizer_impact or "pharmacogene variant"
    reduction = min(80, int(round(max(a_gen, 0.5) * 100)))
    cards.append(
      DecisionCard(
        kind="genetic_filter",
        title="Patient filter (genetic screening)",
        body=(
          f"Genetic driver detected ({gene}). Screen / exclude poor metabolizers to potentially "
          f"eliminate ~{reduction}% of severe {pt_string} events in subsequent cohorts."
        ),
        priority=1,
      )
    )

  if rising_signal:
    cards.append(
      DecisionCard(
        kind="rising",
        title="Rising signal",
        body=(
          f"Signal velocity elevated for {drug_name} ↔ {pt_string} across recent FAERS periods. "
          "Prioritize for weekly PV triage before the next aggregate report."
        ),
        priority=0,
      )
    )

  if literature_confirmed or label_sources:
    src = ", ".join(label_sources or []) or "literature"
    cards.append(
      DecisionCard(
        kind="literature",
        title="Evidence corroboration",
        body=(
          f"Disproportionality for {drug_name} ↔ {pt_string} is backed by {src}. "
          "Treat as hypothesis support — not causality. Cross-check PubMed / label / OT LRT before escalation."
        ),
        priority=2,
      )
    )

  if fused >= settings.action_fused_threshold or is_bbw:
    cards.append(
      DecisionCard(
        kind="regulatory",
        title="Regulatory response export",
        body=(
          "Fused risk and/or labeled risk warrants an audit pack. "
          "Export DSUR/PBRER draft sections and evidence JSON for safety committee review."
        ),
        priority=2,
      )
    )

  cards.sort(key=lambda c: c.priority)
  return cards


def protocol_exclusion_clause(
  *,
  drug_name: str,
  pt_string: str,
  gene_symbol: str,
  metabolizer_impact: str | None,
  estimated_reduction: float,
) -> tuple[str, str]:
  impact = metabolizer_impact or f"{gene_symbol} loss-of-function"
  clause = (
    f"Exclusion: Subjects with known {impact} genotype "
    f"(e.g., {gene_symbol} poor metabolizer status) will be excluded from enrollment "
    f"due to elevated risk of {pt_string} observed with {drug_name}."
  )
  rationale = (
    f"QSLRM genetic attribution and historical AE enrichment suggest excluding {impact} "
    f"may reduce severe {pt_string} by approximately {int(estimated_reduction * 100)}%."
  )
  return clause, rationale


def action_flag_from_cards(cards: list[DecisionCard], fused: float | None, rising: bool) -> tuple[bool, str | None]:
  settings = get_settings()
  if rising:
    return True, "RISING"
  if any(c.kind == "genetic_filter" for c in cards):
    return True, "GENETIC_FILTER"
  if any(c.kind == "dose" for c in cards):
    return True, "DOSE_REVIEW"
  if (fused or 0) >= settings.action_fused_threshold:
    return True, "HIGH_RISK"
  return False, None
