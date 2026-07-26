"""DSUR / PBRER draft package generator (structured HTML + JSON evidence)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fusion.decisions import build_decisions
from qslrm_erd.models import (
  AeTerm,
  DdiRisk,
  DemographicSignal,
  Drug,
  GroundTruthLabel,
  OmicScore,
  ProtocolExclusion,
  RiskScore,
  SignalStat,
  SignalVelocity,
  TrialAe,
  TrialOnsetCurve,
)
from qslrm_erd.settings import get_settings


def build_dsur_payload(
  session: Session,
  *,
  drug_id: str | None = None,
  limit: int = 25,
) -> dict[str, Any]:
  settings = get_settings()
  q = (
    select(RiskScore)
    .where(
      RiskScore.model_version == settings.model_version,
      RiskScore.fused_score.is_not(None),
    )
    .order_by(RiskScore.fused_score.desc())
    .limit(limit)
  )
  if drug_id:
    q = q.where(RiskScore.drug_id == drug_id)
  rows = session.scalars(q).all()

  sections: list[dict[str, Any]] = []
  for rs in rows:
    drug = session.get(Drug, rs.drug_id)
    ae = session.get(AeTerm, rs.ae_term_id)
    om = session.scalar(
      select(OmicScore).where(
        OmicScore.drug_id == rs.drug_id,
        OmicScore.ae_term_id == rs.ae_term_id,
        OmicScore.model_version == rs.model_version,
      )
    )
    sig = session.scalar(
      select(SignalStat).where(
        SignalStat.drug_id == rs.drug_id,
        SignalStat.ae_term_id == rs.ae_term_id,
        SignalStat.period == "all",
        SignalStat.model_version == rs.model_version,
      )
    )
    vel = session.scalar(
      select(SignalVelocity).where(
        SignalVelocity.drug_id == rs.drug_id,
        SignalVelocity.ae_term_id == rs.ae_term_id,
        SignalVelocity.model_version == rs.model_version,
      )
    )
    excl = session.scalars(
      select(ProtocolExclusion).where(
        ProtocolExclusion.drug_id == rs.drug_id,
        ProtocolExclusion.ae_term_id == rs.ae_term_id,
      )
    ).all()
    demos = session.scalars(
      select(DemographicSignal).where(
        DemographicSignal.drug_id == rs.drug_id,
        DemographicSignal.ae_term_id == rs.ae_term_id,
        DemographicSignal.model_version == rs.model_version,
      )
    ).all()
    cards = build_decisions(
      drug_name=drug.preferred_name if drug else rs.drug_id,
      pt_string=ae.pt_string if ae else rs.ae_term_id,
      fused_score=rs.fused_score,
      attr_dose=rs.attr_dose,
      attr_offtarget=rs.attr_offtarget,
      attr_transcriptomic=rs.attr_transcriptomic,
      attr_genetic=rs.attr_genetic,
      rising_signal=bool(rs.rising_signal),
      is_bbw=session.scalar(
        select(GroundTruthLabel).where(
          GroundTruthLabel.drug_id == rs.drug_id,
          GroundTruthLabel.ae_term_id == rs.ae_term_id,
        )
      )
      is not None,
    )
    sections.append(
      {
        "drug_id": rs.drug_id,
        "drug_name": drug.preferred_name if drug else rs.drug_id,
        "ae_term_id": rs.ae_term_id,
        "pt_string": ae.pt_string if ae else rs.ae_term_id,
        "fused_score": rs.fused_score,
        "prr": rs.prr,
        "ror": rs.ror,
        "n_reports": rs.n_reports,
        "serious_rate": rs.serious_rate,
        "ebgm": sig.ebgm if sig else None,
        "rising_signal": rs.rising_signal,
        "action_flag": rs.action_flag,
        "attribution": {
          "dose": rs.attr_dose,
          "offtarget": rs.attr_offtarget,
          "transcriptomic": rs.attr_transcriptomic,
          "genetic": rs.attr_genetic,
        },
        "omic": {
          "s_off": om.s_off if om else None,
          "s_path": om.s_path if om else None,
          "s_trans": om.s_trans if om else None,
          "s_gen": om.s_gen if om else None,
          "omic_risk": om.omic_risk if om else rs.omic_risk,
        },
        "velocity": None
        if vel is None
        else {
          "period_from": vel.period_from,
          "period_to": vel.period_to,
          "delta_ror": vel.delta_ror,
          "velocity": vel.velocity,
          "rising": vel.rising,
        },
        "protocol_exclusions": [
          {"clause": e.clause_text, "rationale": e.rationale, "adr_reduction": e.estimated_adr_reduction}
          for e in excl
        ],
        "demographics": [
          {
            "type": d.stratum_type,
            "value": d.stratum_value,
            "n": d.n_reports,
            "share": d.share,
            "lift": d.lift_vs_background,
          }
          for d in demos
        ],
        "decisions": [{"kind": c.kind, "title": c.title, "body": c.body} for c in cards],
      }
    )

  ddi = [
    {
      "drug_id": d.drug_id,
      "concomitant": d.concomitant_name,
      "enzyme": d.enzyme,
      "risk_level": d.risk_level,
      "mechanism": d.mechanism,
    }
    for d in session.scalars(select(DdiRisk).limit(50)).all()
  ]

  return {
    "document": "DSUR/PBRER draft package",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "model_version": settings.model_version,
    "disclaimer": (
      "DRAFT ONLY — Hypothesis triage outputs. Not a final DSUR/PBRER submission. "
      "Disproportionality ≠ causality. Requires medical review before regulatory filing."
    ),
    "sections": sections,
    "ddi_matrix": ddi,
    "trial_ae_count": int(session.scalar(select(func.count()).select_from(TrialAe)) or 0),
    "onset_curve_points": int(session.scalar(select(func.count()).select_from(TrialOnsetCurve)) or 0),
  }


def render_dsur_html(payload: dict[str, Any]) -> str:
  rows = []
  for s in payload.get("sections") or []:
    cards = "".join(
      f"<li><strong>{c['title']}</strong> — {c['body']}</li>" for c in s.get("decisions") or []
    )
    excl = "".join(f"<blockquote>{e['clause']}</blockquote>" for e in s.get("protocol_exclusions") or [])
    rows.append(
      f"""
      <section class="pair">
        <h2>{s['drug_name']} ↔ {s['pt_string']}</h2>
        <p>Fused {s.get('fused_score'):.1f} · PRR {s.get('prr')} · ROR {s.get('ror')} ·
           flag {s.get('action_flag') or '—'} · rising={s.get('rising_signal')}</p>
        <h3>Decisions</h3><ul>{cards or '<li>None</li>'}</ul>
        <h3>Suggested protocol exclusions</h3>{excl or '<p>None generated.</p>'}
      </section>
      """
    )
  ddi_rows = "".join(
    f"<tr><td>{d['drug_id']}</td><td>{d['concomitant']}</td><td>{d['enzyme']}</td>"
    f"<td>{d['risk_level']}</td><td>{d['mechanism']}</td></tr>"
    for d in payload.get("ddi_matrix") or []
  )
  return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>QSLRM DSUR/PBRER Draft</title>
<style>
body{{font-family:Georgia,serif;max-width:880px;margin:2rem auto;padding:0 1rem;color:#1a1a1a}}
h1{{font-size:1.6rem}} .warn{{background:#fff3cd;padding:.75rem 1rem;border-left:4px solid #c9a227}}
table{{border-collapse:collapse;width:100%}} td,th{{border:1px solid #ccc;padding:.4rem;font-size:.9rem}}
blockquote{{border-left:3px solid #0d7377;padding-left:.75rem;color:#333}}
</style></head><body>
<h1>QSLRM — DSUR / PBRER Draft Package</h1>
<p class="warn">{payload.get('disclaimer')}</p>
<p>Generated {payload.get('generated_at')} · model {payload.get('model_version')}</p>
{''.join(rows)}
<h2>DDI risk matrix</h2>
<table><thead><tr><th>Drug</th><th>Concomitant</th><th>Enzyme</th><th>Risk</th><th>Mechanism</th></tr></thead>
<tbody>{ddi_rows or '<tr><td colspan="5">No overlaps</td></tr>'}</tbody></table>
</body></html>"""
