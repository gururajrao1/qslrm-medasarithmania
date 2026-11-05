"""FastAPI — decision queue, deep-dive inspector, DSUR export + static UI."""

from __future__ import annotations

import asyncio
import csv
import functools
import io
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from fusion.calibration import fused_band as _fused_band
from fusion.calibration import load_reference
from fusion.decisions import build_decisions, protocol_exclusion_clause
from fusion.dsur import build_dsur_payload, render_dsur_html
from fusion.scoring import signal_strength, zscore
from ingest.sec_edgar import directory_coverage as sec_edgar_coverage
from ingest.sources import sources_manifest
from qslrm_erd.db import get_engine
from qslrm_erd.models import (
  AeTerm,
  DdiRisk,
  DemographicSignal,
  Drug,
  DrugTarget,
  EventLedger,
  GroundTruthLabel,
  LiteratureEvidence,
  NarrativeEntity,
  OmicScore,
  ProtocolExclusion,
  PvCase,
  PvDrugEvent,
  RiskScore,
  SideEffectLabel,
  SignalStat,
  SignalVelocity,
  Target,
  TranscriptSignature,
  TrialAe,
  TrialOnsetCurve,
  Variant,
)
from qslrm_erd.seeds.kinase_mvp import SPONSOR_DIRECTORY
from qslrm_erd.settings import get_settings
from stream import ledger as stream_ledger

WEB_DIR = Path(__file__).resolve().parents[1] / "web"

@asynccontextmanager
async def _lifespan(_: FastAPI):
  stream_ledger.set_event_loop(asyncio.get_running_loop())
  Base = __import__("qslrm_erd.models", fromlist=["Base"]).Base
  Base.metadata.create_all(get_engine(), tables=[EventLedger.__table__])
  yield


app = FastAPI(
  title="QSLRM API",
  description="Hypothesis triage & decision engine — not a causality oracle.",
  version="1.0.1",
  lifespan=_lifespan,
)


@asynccontextmanager
async def _legacy_startup_block_unused():
  """Inert placeholder — startup moved to the _lifespan lifespan handler above."""
  yield
  stream_ledger.set_event_loop(asyncio.get_running_loop())
  # Ensure ledger table exists on existing SQLite DBs
  Base = __import__("qslrm_erd.models", fromlist=["Base"]).Base
  Base.metadata.create_all(get_engine(), tables=[EventLedger.__table__])


app.add_middleware(
  CORSMiddleware,
  allow_origins=get_settings().cors_origins(),
  allow_credentials=True,
  allow_methods=["GET", "POST"],
  allow_headers=["*"],
  max_age=600,
)


def get_db():
  engine = get_engine()
  session = Session(engine)
  try:
    yield session
  finally:
    session.close()


def _row_to_item(
  rs: RiskScore,
  drug: Drug | None,
  ae: AeTerm | None,
  sig: SignalStat | None,
  om: OmicScore | None,
  vel: SignalVelocity | None,
) -> dict[str, Any]:
  """Pure projection of one queue row: no queries, shared by list + single GET."""
  return {
    "drug_id": rs.drug_id,
    "drug_name": drug.preferred_name if drug else rs.drug_id,
    "brand_name": drug.brand_name if drug else None,
    "sponsor_company": drug.sponsor_company if drug else None,
    "molecule_type": drug.molecule_type if drug else None,
    "therapeutic_class": drug.therapeutic_class if drug else None,
    "drug_class": drug.drug_class if drug else None,
    "nda_bla": drug.nda_bla if drug else None,
    "chembl_id": drug.chembl_id if drug else None,
    "ae_term_id": rs.ae_term_id,
    "pt_string": ae.pt_string if ae else rs.ae_term_id,
    "n_reports": rs.n_reports,
    "prr": rs.prr,
    "ror": rs.ror,
    "ebgm": sig.ebgm if sig else None,
    "prr_chi2": getattr(sig, "prr_chi2", None) if sig else None,
    "prr_ci_low": getattr(sig, "prr_ci_low", None) if sig else None,
    "prr_ci_high": getattr(sig, "prr_ci_high", None) if sig else None,
    "ic025": getattr(sig, "ic025", None) if sig else None,
    "eb05": getattr(sig, "eb05", None) if sig else None,
    "eb95": getattr(sig, "eb95", None) if sig else None,
    "ic": sig.ic if sig else None,
    "serious_rate": rs.serious_rate,
    "omic_risk": rs.omic_risk,
    "dose_risk": rs.dose_risk,
    "fused_score": rs.fused_score,
    "attr_dose": rs.attr_dose,
    "attr_offtarget": rs.attr_offtarget,
    "attr_transcriptomic": rs.attr_transcriptomic,
    "attr_genetic": rs.attr_genetic,
    "action_needed": rs.action_needed,
    "action_flag": rs.action_flag,
    "rising_signal": rs.rising_signal,
    # Never blank ΔROR / velocity in UI — fallback 0.0 when no quarterly pair
    "delta_ror": float(vel.delta_ror) if vel is not None else 0.0,
    "signal_velocity": float(vel.velocity) if vel is not None else 0.0,
    "s_off": om.s_off if om else None,
    "s_path": om.s_path if om else None,
    "s_trans": om.s_trans if om else None,
    "s_gen": om.s_gen if om else None,
    "omic_engine": om.engine if om else None,
    "model_version": rs.model_version,
  }



def _enrich_row(session: Session, rs: RiskScore) -> dict[str, Any]:
  drug = session.get(Drug, rs.drug_id)
  ae = session.get(AeTerm, rs.ae_term_id)
  sig = session.scalar(
    select(SignalStat).where(
      SignalStat.drug_id == rs.drug_id,
      SignalStat.ae_term_id == rs.ae_term_id,
      SignalStat.period == "all",
      SignalStat.model_version == rs.model_version,
    )
  )
  om = session.scalar(
    select(OmicScore).where(
      OmicScore.drug_id == rs.drug_id,
      OmicScore.ae_term_id == rs.ae_term_id,
      OmicScore.model_version == rs.model_version,
    )
  )
  vel = session.scalar(
    select(SignalVelocity).where(
      SignalVelocity.drug_id == rs.drug_id,
      SignalVelocity.ae_term_id == rs.ae_term_id,
      SignalVelocity.model_version == rs.model_version,
    )
  )
  return _row_to_item(rs, drug, ae, sig, om, vel)


@app.get("/health")
def health(session: Session = Depends(get_db)) -> dict:  # noqa: B008 -- FastAPI DI requires call-in-default
  s0 = get_settings()
  try:
    fused_pairs = int(session.scalar(select(func.count()).select_from(RiskScore).where(RiskScore.model_version == s0.model_version, RiskScore.fused_score.is_not(None))) or 0)
    db_ok = True
  except Exception:  # noqa: BLE001 -- degraded health instead of 500
    fused_pairs = 0
    db_ok = False
  s = get_settings()
  return {
    "status": "ok" if db_ok else "degraded",
    "db_ok": db_ok,
    "fused_pairs": fused_pairs,
    "product": "QSLRM",
    "mvp_drug_class": s.mvp_drug_class,
    "model_version": s.model_version,
    "claim": "Hypothesis triage — disproportionality ≠ causality",
    "modules": [
      "genetic_eligibility",
      "time_to_onset",
      "ddi_matrix",
      "signal_velocity",
      "narrative_nlp",
      "demographic_strata",
      "dsur_draft",
      "event_ledger",
      "websocket_stream",
    ],
  }


@app.get("/v1/sources")
def list_sources() -> dict:
  return {
    "sources": sources_manifest(),
    "note": "Live clients in ingest/*; offline fixtures under tests/fixtures/phase1.",
  }


def _ttl_cache(ttl_seconds: int = 60, key=None):
  """Tiny TTL cache for expensive read endpoints (keyed per database)."""
  store: dict[Any, tuple[float, Any]] = {}

  def wrap(fn):
    @functools.wraps(fn)
    def inner(*a, **k):
      ck = key() if key else ()
      hit = store.get(ck)
      now = time.time()
      if hit and now - hit[0] < ttl_seconds:
        return hit[1]
      val = fn(*a, **k)
      store[ck] = (now, val)
      return val

    return inner

  return wrap


def _catalog_cache_key() -> tuple[str, str]:
  return (str(get_engine().url), get_settings().model_version)


@app.get("/v1/catalog")
@_ttl_cache(60, key=_catalog_cache_key)
def catalog(session: Session = Depends(get_db)) -> dict:  # noqa: B008 -- FastAPI DI requires call-in-default
  """Frontpage inventory — proves multi-source spine is populated."""
  from sqlalchemy import func

  def n(model) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)

  settings = get_settings()
  fused = int(
    session.scalar(
      select(func.count()).select_from(RiskScore).where(
        RiskScore.model_version == settings.model_version,
        RiskScore.fused_score.is_not(None),
      )
    )
    or 0
  )
  rising = int(
    session.scalar(
      select(func.count()).select_from(RiskScore).where(
        RiskScore.model_version == settings.model_version,
        RiskScore.rising_signal.is_(True),
      )
    )
    or 0
  )
  sponsors = list(SPONSOR_DIRECTORY)
  for d in session.scalars(select(Drug).where(Drug.sponsor_company.is_not(None))).all():
    if d.sponsor_company and d.sponsor_company not in sponsors:
      sponsors.append(d.sponsor_company)
  sponsors = sorted(set(sponsors))

  # Pair counts per sponsor in one GROUP BY (no per-row session.get).
  sponsor_counts: dict[str, int] = {s: 0 for s in sponsors}
  for sponsor_name, pair_count in session.execute(
    select(Drug.sponsor_company, func.count(RiskScore.drug_id))
    .join(RiskScore, RiskScore.drug_id == Drug.drug_id)
    .where(
      RiskScore.model_version == settings.model_version,
      RiskScore.fused_score.is_not(None),
      Drug.sponsor_company.is_not(None),
    )
    .group_by(Drug.sponsor_company)
  ).all():
    if sponsor_name:
      sponsor_counts[sponsor_name] = int(pair_count)
  sponsor_options = [
    {"name": s, "pair_count": sponsor_counts.get(s, 0)}
    for s in sponsors
    if sponsor_counts.get(s, 0) > 0 or s in SPONSOR_DIRECTORY
  ]
  # Prefer populated sponsors first, then alphabetical within groups
  sponsor_options.sort(key=lambda x: (0 if x["pair_count"] > 0 else 1, x["name"].lower()))

  return {
    "model_version": settings.model_version,
    "product": "MedasArithmania / QSLRM",
    "domains": {
      "regulatory": {
        "sponsors": len(sponsors),
        "sponsor_list": sponsors,
        "sponsor_options": sponsor_options,
        "sec_edgar": sec_edgar_coverage(),
        "source": "Sponsor directory + Orange Book / openFDA / RxNorm + SEC EDGAR",
      },
      "transcriptomics": {"transcript_signature": n(TranscriptSignature), "source": "LINCS L1000 + Tox21 + DepMap"},
      "proteomics": {"drug_target": n(DrugTarget), "source": "ChEMBL + BindingDB"},
      "genomics": {"variant": n(Variant), "source": "ClinVar / PharmGKB"},
      "literature": {
        "pubmed_europepmc": n(LiteratureEvidence),
        "sider_labels": n(SideEffectLabel),
        "source": "PubMed / Europe PMC / SIDER / OnSIDES / Open Targets PV / BioDEX",
      },
      "regulatory_orange_book": {
        "drugs_with_nda": int(
          session.scalar(select(func.count()).select_from(Drug).where(Drug.nda_bla.is_not(None))) or 0
        ),
        "source": "FDA Orange Book fixtures",
      },
      "pharmacovigilance": {
        "pv_case": n(PvCase),
        "pv_drug_event": n(PvDrugEvent),
        "signal_velocity": n(SignalVelocity),
        "demographic_signal": n(DemographicSignal),
        "narrative_entity": n(NarrativeEntity),
        "source": "openFDA FAERS + EudraVigilance fixtures",
      },
      "clinical_trials": {
        "trial_ae": n(TrialAe),
        "onset_curve_points": n(TrialOnsetCurve),
        "ddi_risk": n(DdiRisk),
        "protocol_exclusion": n(ProtocolExclusion),
        "source": "ClinicalTrials.gov + CYP DDI",
      },
      "streaming": {
        "event_ledger": n(EventLedger),
        "source": "Append-only ledger + WS /v1/stream (Debezium prod path)",
      },
    },
    "queue": {"fused_pairs": fused, "rising_signals": rising},
    "filters": {
      "sponsors": [s["name"] for s in sponsor_options if s["pair_count"] > 0],
      "sponsor_options": sponsor_options,
      "molecule_types": ["small_molecule", "biologic"],
      "drug_classes": sorted(
        {
          d.drug_class
          for d in session.scalars(select(Drug).where(Drug.drug_class.is_not(None))).all()
          if d.drug_class
        }
      ),
      "regions": ["US", "EU", "Global"],
    },
    "sources": sources_manifest(),
  }


def _enrich_page(
  session: Session, triples: list[tuple[RiskScore, Drug, AeTerm]], model_version: str
) -> list[dict[str, Any]]:
  """Enrich one page with three batched queries (no per-row N+1)."""
  keys = [(rs.drug_id, rs.ae_term_id) for rs, _, _ in triples]
  if not keys:
    return []
  pair_in = tuple_(SignalStat.drug_id, SignalStat.ae_term_id).in_(keys)
  sigs = {
    (s.drug_id, s.ae_term_id): s
    for s in session.scalars(
      select(SignalStat).where(
        pair_in, SignalStat.period == "all", SignalStat.model_version == model_version
      )
    ).all()
  }
  oms = {
    (o.drug_id, o.ae_term_id): o
    for o in session.scalars(
      select(OmicScore).where(
        tuple_(OmicScore.drug_id, OmicScore.ae_term_id).in_(keys),
        OmicScore.model_version == model_version,
      )
    ).all()
  }
  vels = {
    (v.drug_id, v.ae_term_id): v
    for v in session.scalars(
      select(SignalVelocity).where(
        tuple_(SignalVelocity.drug_id, SignalVelocity.ae_term_id).in_(keys),
        SignalVelocity.model_version == model_version,
      )
    ).all()
  }
  return [
    _row_to_item(rs, drug, ae, sigs.get(key), oms.get(key), vels.get(key))
    for (rs, drug, ae), key in zip(triples, keys, strict=True)
  ]


@app.get("/v1/risk-scores")
def list_risk_scores(
  limit: int = Query(100, ge=1, le=500),
  offset: int = Query(0, ge=0),
  action_needed: bool | None = Query(None),
  rising_only: bool = Query(False),
  sponsor: str | None = Query(None),
  molecule_type: str | None = Query(None),
  drug_class: str | None = Query(None),
  min_fused: float | None = Query(None, ge=0, le=100),
  min_n: int | None = Query(None, ge=1),
  region: str | None = Query(None, description="US | EU | Global — filters pairs with PV cases in region"),
  q: str | None = Query(None, description="Search drug or ADR"),
  sort: str = Query("fused", pattern="^(fused|velocity|serious|n|ebgm|ic)$"),
  session: Session = Depends(get_db),  # noqa: B008 -- FastAPI DI requires call-in-default
) -> dict:
  settings = get_settings()
  mv = settings.model_version
  qset = (
    select(RiskScore, Drug, AeTerm)
    .join(Drug, Drug.drug_id == RiskScore.drug_id)
    .join(AeTerm, AeTerm.ae_term_id == RiskScore.ae_term_id)
    .where(
      RiskScore.model_version == mv,
      RiskScore.fused_score.is_not(None),
    )
  )
  if action_needed is not None:
    qset = qset.where(RiskScore.action_needed.is_(action_needed))
  if rising_only:
    qset = qset.where(RiskScore.rising_signal.is_(True))
  if sponsor:
    qset = qset.where(func.lower(Drug.sponsor_company) == sponsor.lower())
  if molecule_type:
    qset = qset.where(Drug.molecule_type == molecule_type)
  if drug_class:
    qset = qset.where(Drug.drug_class == drug_class)
  if min_fused is not None:
    qset = qset.where(RiskScore.fused_score >= min_fused)
  if min_n is not None:
    qset = qset.where(RiskScore.n_reports >= min_n)
  if q and q.strip():
    like = f"%{q.strip()}%"
    qset = qset.where(
      Drug.preferred_name.ilike(like)
      | AeTerm.pt_string.ilike(like)
      | Drug.sponsor_company.ilike(like)
      | Drug.brand_name.ilike(like)
    )
  if sort == "serious":
    qset = qset.order_by(RiskScore.serious_rate.desc().nullslast(), RiskScore.fused_score.desc())
  elif sort == "n":
    qset = qset.order_by(RiskScore.n_reports.desc(), RiskScore.fused_score.desc())
  elif sort == "velocity":
    qset = qset.outerjoin(
      SignalVelocity,
      (SignalVelocity.drug_id == RiskScore.drug_id)
      & (SignalVelocity.ae_term_id == RiskScore.ae_term_id)
      & (SignalVelocity.model_version == mv),
    ).order_by(SignalVelocity.velocity.desc().nullslast(), RiskScore.fused_score.desc())
  elif sort in ("ebgm", "ic"):
    _col = SignalStat.ebgm if sort == "ebgm" else SignalStat.ic
    qset = qset.outerjoin(
      SignalStat,
      (SignalStat.drug_id == RiskScore.drug_id)
      & (SignalStat.ae_term_id == RiskScore.ae_term_id)
      & (SignalStat.period == "all")
      & (SignalStat.model_version == mv),
    ).order_by(_col.desc().nullslast(), RiskScore.fused_score.desc())
  else:
    qset = qset.order_by(RiskScore.fused_score.desc())
  triples = session.execute(qset).all()
  rows = [(rs, drug, ae) for rs, drug, ae in triples]
  if region:
    region_key = "Global" if region.upper() == "GLOBAL" else region.upper()
    region_pairs = {
      (r.drug_id, r.ae_term_id)
      for r in session.scalars(
        select(PvDrugEvent).where(
          PvDrugEvent.case_id.in_(
            select(PvCase.case_id).where(PvCase.source_region == region_key)
          )
        )
      ).all()
    }
    rows = [t for t in rows if (t[0].drug_id, t[0].ae_term_id) in region_pairs]
  total = len(rows)
  rising_all = sum(1 for rs, _, _ in rows if rs.rising_signal)
  page = rows[offset : offset + limit]
  items = _enrich_page(session, page, mv)
  for pos, item in enumerate(items, start=offset + 1):
    item["rank"] = pos
  rising_n = sum(1 for it in items if it["rising_signal"])
  return {
    "items": items,
    "limit": limit,
    "offset": offset,
    "total": total,
    "rising_count": rising_all,
    "rising_count_page": rising_n,
    "model_version": settings.model_version,
    "sort": sort,
    "disclaimer": "Disproportionality ≠ causality. Ranked hypotheses for triage only.",
  }


@app.get("/v1/risk-scores/{drug_id}/{ae_term_id}")
def get_risk_score(drug_id: str, ae_term_id: str, session: Session = Depends(get_db)) -> dict:  # noqa: B008 -- FastAPI DI requires call-in-default
  settings = get_settings()
  rs = session.scalar(
    select(RiskScore).where(
      RiskScore.drug_id == drug_id,
      RiskScore.ae_term_id == ae_term_id,
      RiskScore.model_version == settings.model_version,
    )
  )
  if rs is None:
    raise HTTPException(status_code=404, detail="risk score not found")
  return _enrich_row(session, rs)


@app.get("/v1/deep-dive/{drug_id}/{ae_term_id}")
def deep_dive(drug_id: str, ae_term_id: str, session: Session = Depends(get_db)) -> dict:  # noqa: B008 -- FastAPI DI requires call-in-default
  settings = get_settings()
  rs = session.scalar(
    select(RiskScore).where(
      RiskScore.drug_id == drug_id,
      RiskScore.ae_term_id == ae_term_id,
      RiskScore.model_version == settings.model_version,
    )
  )
  if rs is None:
    raise HTTPException(status_code=404, detail="risk score not found")

  base = _enrich_row(session, rs)
  drug = session.get(Drug, drug_id)
  _ae = session.get(AeTerm, ae_term_id)
  is_bbw = (
    session.scalar(
      select(GroundTruthLabel).where(
        GroundTruthLabel.drug_id == drug_id,
        GroundTruthLabel.ae_term_id == ae_term_id,
      )
    )
    is not None
  )

  lit_rows = session.scalars(
    select(LiteratureEvidence).where(LiteratureEvidence.drug_id == drug_id)
  ).all()
  sider_rows = session.scalars(
    select(SideEffectLabel).where(SideEffectLabel.drug_id == drug_id)
  ).all()
  lit_pair = [x for x in lit_rows if x.ae_term_id == ae_term_id and x.relation_confirmed]
  label_pair = [x for x in sider_rows if x.ae_term_id == ae_term_id]
  label_sources = sorted({x.source for x in label_pair})
  if lit_pair:
    label_sources = sorted(set(label_sources) | {x.source for x in lit_pair})

  _all_variants = session.scalars(select(Variant)).all()
  _pt_lower = (base.get("pt_string") or "").lower()
  _scoped_variants = [
    v for v in _all_variants if _pt_lower and (v.related_pt or "").lower() == _pt_lower
  ][:25]
  _card_metabolizer_impact = next(
    (v.metabolizer_impact for v in _scoped_variants if v.metabolizer_impact), None
  )
  if _card_metabolizer_impact is None:
    _card_metabolizer_impact = next(
      (v.metabolizer_impact for v in _all_variants if v.metabolizer_impact), None
    )
  cards = build_decisions(
    drug_name=base["drug_name"],
    pt_string=base["pt_string"],
    fused_score=rs.fused_score,
    attr_dose=rs.attr_dose,
    attr_offtarget=rs.attr_offtarget,
    attr_transcriptomic=rs.attr_transcriptomic,
    attr_genetic=rs.attr_genetic,
    rising_signal=bool(rs.rising_signal),
    is_bbw=is_bbw,
    literature_confirmed=bool(lit_pair),
    label_sources=label_sources or None,
    metabolizer_impact=_card_metabolizer_impact,
  )

  proteomics = []
  for dt in session.scalars(select(DrugTarget).where(DrugTarget.drug_id == drug_id)).all():
    tgt = session.get(Target, dt.target_id)
    proteomics.append(
      {
        "target_id": dt.target_id,
        "gene_symbol": tgt.gene_symbol if tgt else dt.target_id,
        "affinity_nm": dt.affinity_nm,
        "is_off_target": dt.is_off_target,
        "action_type": dt.action_type,
        "pdb_id": tgt.pdb_id if tgt else None,
        "uniprot_id": tgt.uniprot_id if tgt else None,
      }
    )

  transcriptomics = [
    {
      "gene_symbol": t.gene_symbol,
      "z_score": t.z_score,
      "tox_weight": t.tox_weight,
      "direction": t.direction,
      "source": t.source,
    }
    for t in session.scalars(
      select(TranscriptSignature).where(TranscriptSignature.drug_id == drug_id)
    ).all()
  ]

  genomics = [
    {
      "variant_id": v.variant_id,
      "rsid": v.rsid,
      "gene_symbol": v.gene_symbol,
      "metabolizer_impact": v.metabolizer_impact,
      "effect_size": v.effect_size,
      "related_pt": v.related_pt,
    }
    for v in _scoped_variants
  ]

  trials = [
    {
      "nct_id": t.nct_id,
      "phase": t.phase,
      "arm": t.arm,
      "event_count": t.event_count,
      "subjects_at_risk": t.subjects_at_risk,
      "median_onset_weeks": t.median_onset_weeks,
      "dose_text": t.dose_text,
      "ae_term_id": t.ae_term_id,
    }
    for t in session.scalars(
      select(TrialAe).where(TrialAe.drug_id == drug_id, TrialAe.ae_term_id == ae_term_id)
    ).all()
  ]
  if not trials:
    trials = [
      {
        "nct_id": t.nct_id,
        "phase": t.phase,
        "arm": t.arm,
        "event_count": t.event_count,
        "subjects_at_risk": t.subjects_at_risk,
        "median_onset_weeks": t.median_onset_weeks,
        "dose_text": t.dose_text,
        "ae_term_id": t.ae_term_id,
      }
      for t in session.scalars(select(TrialAe).where(TrialAe.drug_id == drug_id).limit(25)).all()
    ]

  onset = [
    {"week": c.week, "survival_prob": c.survival_prob, "event_prob": c.event_prob, "nct_id": c.nct_id}
    for c in session.scalars(
      select(TrialOnsetCurve)
      .where(TrialOnsetCurve.drug_id == drug_id, TrialOnsetCurve.ae_term_id == ae_term_id)
      .order_by(TrialOnsetCurve.week)
    ).all()
  ]
  if not onset:
    # fall back to any onset curve for this drug so KM panel is never empty
    any_curve = session.scalars(
      select(TrialOnsetCurve).where(TrialOnsetCurve.drug_id == drug_id).order_by(TrialOnsetCurve.week).limit(40)
    ).all()
    onset = [
      {"week": c.week, "survival_prob": c.survival_prob, "event_prob": c.event_prob, "nct_id": c.nct_id}
      for c in any_curve
    ]

  ddi = [
    {
      "concomitant": d.concomitant_name,
      "enzyme": d.enzyme,
      "risk_level": d.risk_level,
      "mechanism": d.mechanism,
      "notes": d.notes,
    }
    for d in session.scalars(select(DdiRisk).where(DdiRisk.drug_id == drug_id)).all()
  ]

  velocity = session.scalar(
    select(SignalVelocity).where(
      SignalVelocity.drug_id == drug_id,
      SignalVelocity.ae_term_id == ae_term_id,
      SignalVelocity.model_version == settings.model_version,
    )
  )

  demos = [
    {
      "stratum_type": d.stratum_type,
      "stratum_value": d.stratum_value,
      "n_reports": d.n_reports,
      "share": d.share,
      "lift_vs_background": d.lift_vs_background,
    }
    for d in session.scalars(
      select(DemographicSignal).where(
        DemographicSignal.drug_id == drug_id,
        DemographicSignal.ae_term_id == ae_term_id,
        DemographicSignal.model_version == settings.model_version,
      )
    ).all()
  ]

  case_ids = [
    r.case_id
    for r in session.scalars(
      select(PvDrugEvent).where(
        PvDrugEvent.drug_id == drug_id, PvDrugEvent.ae_term_id == ae_term_id
      )
    ).all()
  ]
  narratives = []
  entities = []
  for cid in case_ids[:20]:
    case = session.get(PvCase, cid)
    if case and case.narrative:
      narratives.append({"case_id": cid, "narrative": case.narrative, "country": case.country})
    for ent in session.scalars(select(NarrativeEntity).where(NarrativeEntity.case_id == cid)).all():
      entities.append(
        {
          "case_id": cid,
          "entity_type": ent.entity_type,
          "entity_text": ent.entity_text,
          "confidence": ent.confidence,
          "extractor": ent.extractor,
        }
      )

  protocol = [
    {
      "variant_id": p.variant_id,
      "clause_text": p.clause_text,
      "rationale": p.rationale,
      "estimated_adr_reduction": p.estimated_adr_reduction,
    }
    for p in session.scalars(
      select(ProtocolExclusion).where(
        ProtocolExclusion.drug_id == drug_id, ProtocolExclusion.ae_term_id == ae_term_id
      )
    ).all()
  ]

  # Class comparison: same MedDRA PT across kinase class competitors
  peers = session.scalars(
    select(RiskScore).where(
      RiskScore.ae_term_id == ae_term_id,
      RiskScore.model_version == settings.model_version,
      RiskScore.fused_score.is_not(None),
    )
  ).all()
  _peer_drugs = {
    d.drug_id: d
    for d in session.scalars(
      select(Drug).where(Drug.drug_id.in_([p.drug_id for p in peers]))
    ).all()
  }
  class_comparison = []
  for peer in peers:
    pd = _peer_drugs.get(peer.drug_id)
    if not pd or pd.drug_class != (drug.drug_class if drug else "kinase_inhibitor"):
      continue
    class_comparison.append(
      {
        "drug_id": peer.drug_id,
        "drug_name": pd.preferred_name,
        "sponsor_company": pd.sponsor_company,
        "fused_score": peer.fused_score,
        "attr_dose": peer.attr_dose,
        "attr_offtarget": peer.attr_offtarget,
        "attr_transcriptomic": peer.attr_transcriptomic,
        "attr_genetic": peer.attr_genetic,
        "is_selected": peer.drug_id == drug_id,
        "rising_signal": peer.rising_signal,
        "action_flag": peer.action_flag,
      }
    )
  class_comparison.sort(key=lambda x: -(x["fused_score"] or 0))

  literature = [
    {
      "pmid": lit.pmid,
      "title": lit.title,
      "year": lit.year,
      "source": lit.source,
      "citation_count": lit.citation_count,
      "snippet": lit.abstract_snippet,
      "relation_confirmed": lit.relation_confirmed,
      "extractor": lit.extractor,
      "ae_term_id": lit.ae_term_id,
      "matches_pair": lit.ae_term_id == ae_term_id,
    }
    for lit in lit_rows
  ]
  literature.sort(key=lambda x: (not x["matches_pair"], -(x["citation_count"] or 0)))

  _sider_aes = {
    a.ae_term_id: a
    for a in session.scalars(
      select(AeTerm).where(AeTerm.ae_term_id.in_([s.ae_term_id for s in sider_rows]))
    ).all()
  }
  sider = [
    {
      "ae_term_id": s.ae_term_id,
      "pt_string": (_sider_aes[s.ae_term_id].pt_string if s.ae_term_id in _sider_aes else s.ae_term_id),
      "frequency": s.frequency,
      "source": s.source,
      "matches_pair": s.ae_term_id == ae_term_id,
    }
    for s in sider_rows
  ]
  sider.sort(key=lambda x: (not x["matches_pair"], x["source"] or "", x["pt_string"] or ""))
  _hist_rows = session.scalars(
    select(SignalStat).where(
      SignalStat.drug_id == drug_id,
      SignalStat.ae_term_id == ae_term_id,
      SignalStat.model_version == settings.model_version,
      SignalStat.period != "all",
    )
  ).all()
  velocity_history = [
    {
      "period": h.period,
      "ror": h.ror,
      "ror_ci_low": h.ror_ci_low,
      "ror_ci_high": h.ror_ci_high,
      "n11": h.n11,
    }
    for h in sorted(_hist_rows, key=lambda h: h.period or "")
  ]
  fused_band = None
  _ref = load_reference()
  if _ref and _ref.get("model_version") == settings.model_version and len(_ref.get("stats", [])) == 4:
    try:
      _w = {k: float(_ref["weights"][k]) for k in ("w_signal", "w_omic", "w_dose", "w_serious")}
      _st = [(float(m), float(s)) for m, s in _ref["stats"]]
      _sig_row = session.scalar(
        select(SignalStat).where(
          SignalStat.drug_id == drug_id,
          SignalStat.ae_term_id == ae_term_id,
          SignalStat.period == "all",
          SignalStat.model_version == settings.model_version,
        )
      )
      _om_row = session.scalar(
        select(OmicScore).where(
          OmicScore.drug_id == drug_id,
          OmicScore.ae_term_id == ae_term_id,
          OmicScore.model_version == settings.model_version,
        )
      )
      _strength = signal_strength(
        _sig_row.prr if _sig_row else base["prr"],
        _sig_row.ror if _sig_row else base["ror"],
        _sig_row.ebgm if _sig_row else None,
        ror_ci_low=_sig_row.ror_ci_low if _sig_row else None,
        ic025=getattr(_sig_row, "ic025", None) if _sig_row else None,
        eb05=getattr(_sig_row, "eb05", None) if _sig_row else None,
      )
      _zv = (
        zscore(_strength, *_st[0]),
        zscore(float(_om_row.omic_risk) if _om_row and _om_row.omic_risk is not None else 0.0, *_st[1]),
        zscore(float(rs.dose_risk or 0.0), *_st[2]),
        zscore(float(rs.serious_rate or 0.0), *_st[3]),
      )
      _ov = (
        float(_om_row.s_off) if _om_row else 0.0,
        float(_om_row.s_trans) if _om_row else 0.0,
        float(_om_row.s_gen) if _om_row else 0.0,
      )
      fused_band = _fused_band(_zv, _ov, _w)
    except (TypeError, ValueError, KeyError, AttributeError):
      fused_band = None

  return {
    **base,
    "cyp_substrates": drug.cyp_substrates if drug else None,
    "is_bbw_or_rems": is_bbw,
    "literature_confirmed": bool(lit_pair),
    "evidence_sources": label_sources,
    "decisions": [{"kind": c.kind, "title": c.title, "body": c.body, "priority": c.priority} for c in cards],
    "proteomics": proteomics,
    "transcriptomics": transcriptomics,
    "genomics": genomics,
    "trials": trials,
    "onset_curve": onset,
    "ddi": ddi,
    "velocity": None
    if velocity is None
    else {
      "period_from": velocity.period_from,
      "period_to": velocity.period_to,
      "ror_from": velocity.ror_from,
      "ror_to": velocity.ror_to,
      "delta_ror": velocity.delta_ror,
      "velocity": velocity.velocity,
      "rising": velocity.rising,
    },
    "demographics": demos,
    "narratives": narratives,
    "narrative_entities": entities,
    "protocol_exclusions": protocol,
    "class_comparison": class_comparison,
    "literature": literature,
    "sider_labels": sider,
    "velocity_history": velocity_history,
    "fused_band": fused_band,
    "calibration_source": "frozen" if fused_band is not None else None,
  }


@app.post("/v1/protocol/draft", status_code=201)
def draft_protocol_clause(
  session: Session = Depends(get_db),  # noqa: B008 -- FastAPI DI requires call-in-default
  drug_id: str | None = Query(None),
  ae_term_id: str | None = Query(None),
  payload: dict | None = None,
) -> dict:
  """Generate (or refresh) a draft exclusion clause from the pair's top variant."""
  body = payload or {}
  drug_id = drug_id or body.get("drug_id")
  ae_term_id = ae_term_id or body.get("ae_term_id")
  if not drug_id or not ae_term_id:
    raise HTTPException(status_code=422, detail="drug_id and ae_term_id required (query or JSON body)")
  settings = get_settings()
  rs = session.scalar(
    select(RiskScore).where(
      RiskScore.drug_id == drug_id,
      RiskScore.ae_term_id == ae_term_id,
      RiskScore.model_version == settings.model_version,
    )
  )
  if rs is None:
    raise HTTPException(status_code=404, detail="risk score not found")
  ae = session.get(AeTerm, ae_term_id)
  pt = ae.pt_string if ae else ae_term_id
  variants = session.scalars(select(Variant)).all()
  scoped = [v for v in variants if pt and (v.related_pt or "").lower() == pt.lower()]
  top = next((v for v in scoped if v.metabolizer_impact), None)
  if top is None:
    top = next((v for v in variants if v.metabolizer_impact), None)
  if top is None:
    raise HTTPException(status_code=404, detail="no pharmacogene variant available")
  genetic_mass = float(rs.attr_genetic or 0)
  reduction = min(0.8, max(0.4, genetic_mass if genetic_mass >= 0.4 else 0.55))
  drug = session.get(Drug, drug_id)
  clause, rationale = protocol_exclusion_clause(
    drug_name=drug.preferred_name if drug else drug_id,
    pt_string=pt,
    gene_symbol=top.gene_symbol,
    metabolizer_impact=top.metabolizer_impact,
    estimated_reduction=reduction,
  )
  existing = session.scalar(
    select(ProtocolExclusion).where(
      ProtocolExclusion.drug_id == drug_id,
      ProtocolExclusion.ae_term_id == ae_term_id,
      ProtocolExclusion.variant_id == top.variant_id,
    )
  )
  payload = {
    "drug_id": drug_id,
    "ae_term_id": ae_term_id,
    "variant_id": top.variant_id,
    "clause_text": clause,
    "rationale": rationale,
    "estimated_adr_reduction": reduction,
  }
  created = existing is None
  if created:
    session.add(ProtocolExclusion(**payload))
  else:
    for k, v in payload.items():
      setattr(existing, k, v)
  return {"created": created, "status": "draft", **payload}


@app.get("/v1/dsur")
def dsur_package(
  format: str = Query("json", pattern="^(json|html)$"),
  drug_id: str | None = Query(None),
  limit: int = Query(25, ge=1, le=100),
  session: Session = Depends(get_db),  # noqa: B008 -- FastAPI DI requires call-in-default
):
  payload = build_dsur_payload(session, drug_id=drug_id, limit=limit)
  if format == "html":
    return HTMLResponse(render_dsur_html(payload))
  return JSONResponse(
    payload,
    headers={"Content-Disposition": "attachment; filename=qslrm_dsur_draft.json"},
  )


@app.get("/v1/audit")
def audit_export(
  format: str = Query("json", pattern="^(json|csv)$"),
  limit: int = Query(100, ge=1, le=500),
  sponsor: str | None = Query(None),
  molecule_type: str | None = Query(None),
  drug_class: str | None = Query(None),
  rising_only: bool = Query(False),
  q: str | None = Query(None),
  session: Session = Depends(get_db),  # noqa: B008 -- FastAPI DI requires call-in-default
):
  settings = get_settings()
  rows = session.scalars(
    select(RiskScore)
    .where(
      RiskScore.model_version == settings.model_version,
      RiskScore.fused_score.is_not(None),
    )
    .order_by(RiskScore.fused_score.desc())
    .limit(limit)
  ).all()
  items = [_enrich_row(session, r) for r in rows]
  if sponsor:
    items = [it for it in items if (it["sponsor_company"] or "").lower() == sponsor.lower()]
  if molecule_type:
    items = [it for it in items if it["molecule_type"] == molecule_type]
  if drug_class:
    items = [it for it in items if it["drug_class"] == drug_class]
  if rising_only:
    items = [it for it in items if it["rising_signal"]]
  if q and q.strip():
    needle = q.strip().lower()
    items = [
      it
      for it in items
      if needle in f"{it['drug_name']} {it['pt_string']} {it['sponsor_company']} {it['brand_name']}".lower()
    ]
  for i, item in enumerate(items, start=1):
    item["rank"] = i

  pack = {
    "product": "QSLRM",
    "model_version": settings.model_version,
    "mvp_drug_class": settings.mvp_drug_class,
    "disclaimer": "Hypothesis triage only. Not WHO-UMC causality. Not a replacement for Argus/Vault.",
    "join_grain": "drug ↔ target ↔ openFDA PT",
    "items": items,
  }

  if format == "csv":
    buf = io.StringIO()
    fields = [
      "rank",
      "drug_name",
      "sponsor_company",
      "brand_name",
      "drug_class",
      "pt_string",
      "fused_score",
      "prr",
      "ror",
      "serious_rate",
      "n_reports",
      "attr_dose",
      "attr_offtarget",
      "attr_transcriptomic",
      "attr_genetic",
      "action_flag",
      "delta_ror",
      "signal_velocity",
      "rising_signal",
      "s_off",
      "s_path",
      "s_trans",
      "s_gen",
      "model_version",
    ]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for item in items:
      writer.writerow(item)
    return StreamingResponse(
      iter([buf.getvalue()]),
      media_type="text/csv",
      headers={"Content-Disposition": "attachment; filename=qslrm_audit.csv"},
    )

  return JSONResponse(
    pack,
    headers={"Content-Disposition": "attachment; filename=qslrm_audit.json"},
  )


@app.post("/v1/ingest/cumulative")
def start_cumulative_ingest(
  live: bool = Query(True, description="Hit live public APIs (openFDA, CT.gov, PubMed)"),
  faers_limit: int = Query(25, ge=5, le=100, description="Max FAERS reports per drug"),
  sync: bool = Query(False, description="Run inline (slow) instead of background job"),
  session: Session = Depends(get_db),  # noqa: B008 -- FastAPI DI requires call-in-default
) -> dict:
  """Pull every wired dataset for all MVP drugs and recompute fusion (cumulative upserts)."""
  if sync:
    from ingest.cumulative import run_cumulative_pull

    result = run_cumulative_pull(session, live=live, faers_limit=faers_limit, recompute=True)
    return {"mode": "sync", "status": "done", "result": result}

  from ingest.jobs import start_cumulative_job

  job_id = start_cumulative_job(live=live, faers_limit=faers_limit)
  return {
    "mode": "async",
    "status": "queued",
    "job_id": job_id,
    "poll": f"/v1/ingest/jobs/{job_id}",
    "note": "Cumulative upsert across FAERS + CT.gov + literature, then Phase 2/3 recompute.",
  }


@app.get("/v1/ingest/jobs/{job_id}")
def get_ingest_job(job_id: str) -> dict:
  from ingest.jobs import get_job

  job = get_job(job_id)
  if not job:
    raise HTTPException(404, f"Unknown job {job_id}")
  return job


@app.post("/v1/ingest/jobs/{job_id}/cancel")
def cancel_ingest_job(job_id: str) -> dict:
  from ingest.jobs import cancel_job

  job = cancel_job(job_id)
  if not job:
    raise HTTPException(404, f"Unknown job {job_id}")
  return job


@app.get("/v1/stream/events")
def list_stream_events(
  limit: int = Query(50, ge=1, le=500),
  after_id: int = Query(0, ge=0),
  session: Session = Depends(get_db),  # noqa: B008 -- FastAPI DI requires call-in-default
) -> dict:
  """REST replay of append-only event_ledger (CDC cursor substitute)."""
  rows = stream_ledger.recent_events(session, limit=limit, after_id=after_id)
  return {
    "items": [stream_ledger.ledger_to_patch(r) for r in rows],
    "count": len(rows),
    "note": "Append-only ledger. Production: Debezium CDC on Postgres.",
  }


@app.post("/v1/stream/ingest-tick")
def stream_ingest_tick(
  source: str = Query("demo_worker"),
  drug_id: str | None = Query(None),
  ae_term_id: str | None = Query(None),
  summary: str | None = Query(None),
  session: Session = Depends(get_db),  # noqa: B008 -- FastAPI DI requires call-in-default
) -> dict:
  """Append a synthetic ledger event and broadcast to WS subscribers."""
  settings = get_settings()
  if not drug_id or not ae_term_id:
    rs = session.scalar(
      select(RiskScore)
      .where(
        RiskScore.model_version == settings.model_version,
        RiskScore.fused_score.is_not(None),
      )
      .order_by(RiskScore.fused_score.desc())
      .limit(1)
    )
    if rs:
      drug_id = drug_id or rs.drug_id
      ae_term_id = ae_term_id or rs.ae_term_id
  payload = {
    "tick": True,
    "drug_id": drug_id,
    "ae_term_id": ae_term_id,
    "model_version": settings.model_version,
    "ts": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
  }
  entity_key = f"{drug_id or 'na'}|{ae_term_id or 'na'}|{payload['ts']}"
  row = stream_ledger.append_event(
    session,
    source=(source or "demo_worker")[:64],
    entity_key=entity_key,
    payload=payload,
    event_type="ingest_tick",
    drug_id=drug_id,
    ae_term_id=ae_term_id,
    summary=summary or f"Stream tick · {drug_id}/{ae_term_id}",
    broadcast=True,
  )
  session.commit()
  if row is None:
    return {"inserted": False, "reason": "duplicate"}
  return {"inserted": True, "event": stream_ledger.ledger_to_patch(row)}


@app.websocket("/v1/stream")
async def websocket_stream(ws: WebSocket):
  """Live JSON patches from event_ledger → frontend (streaming MVP)."""
  await ws.accept()
  stream_ledger.register_subscriber(ws)
  await ws.send_text(
    json.dumps(
      {
        "type": "hello",
        "product": "QSLRM",
        "channel": "/v1/stream",
        "claim": "Hypothesis triage — live ledger patches (not causality)",
      }
    )
  )
  try:
    while True:
      # Client may send {"type":"ping"} or we heartbeat
      try:
        msg = await asyncio.wait_for(ws.receive_text(), timeout=25.0)
        if msg:
          try:
            data = json.loads(msg)
          except json.JSONDecodeError:
            data = {"type": "raw", "text": msg}
          if data.get("type") == "ping":
            await ws.send_text(json.dumps({"type": "pong"}))
      except TimeoutError:
        await ws.send_text(json.dumps({"type": "heartbeat"}))
  except WebSocketDisconnect:
    pass
  finally:
    stream_ledger.unregister_subscriber(ws)


@app.get("/", response_class=HTMLResponse)
def ui_index():
  index = WEB_DIR / "index.html"
  if not index.exists():
    return HTMLResponse(
      "<h1>QSLRM</h1><p>UI missing — expected web/index.html</p>",
      status_code=500,
    )
  return HTMLResponse(index.read_text(encoding="utf-8"))


if WEB_DIR.exists():
  app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
