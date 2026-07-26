"""Phase 1 orchestration — ChEMBL, Open Targets, ClinVar, openFDA FAERS."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ingest import chembl, clinvar, faers, loaders, opentargets
from ingest.qc import write_qc_report
from qslrm_erd.models import Drug, DrugTarget, Target
from qslrm_erd.settings import get_settings


def _primary_target_ids(session: Session, drug_id: str) -> set[str]:
  rows = session.scalars(
    select(DrugTarget.target_id).where(
      DrugTarget.drug_id == drug_id,
      DrugTarget.is_off_target.is_(False),
    )
  ).all()
  return set(rows)


def ingest_chembl(session: Session, *, offline_payloads: dict[str, Any] | None = None) -> dict:
  """Pull mechanisms/activities for each MVP drug with a ChEMBL ID."""
  drugs = session.scalars(select(Drug).where(Drug.is_mvp_seed.is_(True))).all()
  stats = {"drugs": 0, "targets_ins": 0, "targets_upd": 0, "dt_ins": 0, "dt_upd": 0, "skipped": 0}
  offline_mode = offline_payloads is not None
  offline = offline_payloads or {}
  target_cache: dict[str, dict] = {}

  for drug in drugs:
    if not drug.chembl_id:
      continue
    stats["drugs"] += 1
    primary = _primary_target_ids(session, drug.drug_id)
    if offline_mode:
      payload = offline.get(drug.chembl_id)
      if not payload:
        stats["skipped"] += 1
        continue
      targets, dts = chembl.build_drug_target_rows(
        drug_id=drug.drug_id,
        chembl_id=drug.chembl_id,
        primary_target_ids=primary,
        activities=payload.get("activities") or [],
        mechanisms=payload.get("mechanisms") or [],
        target_cache=payload.get("targets") or {},
      )
    else:
      targets, dts = chembl.build_drug_target_rows(
        drug_id=drug.drug_id,
        chembl_id=drug.chembl_id,
        primary_target_ids=primary,
        target_cache=target_cache,
      )
    ti, tu = loaders.upsert_targets(session, targets)
    di, du = loaders.upsert_drug_targets(session, dts)
    xwalks = []
    for t in targets:
      if t.get("uniprot_id"):
        xwalks.append(
          {
            "entity_type": "target",
            "from_system": "uniprot",
            "from_id": t["uniprot_id"],
            "to_system": "gene_symbol",
            "to_id": t["gene_symbol"],
            "confidence": 1.0,
          }
        )
    loaders.upsert_crosswalks(session, xwalks)
    stats["targets_ins"] += ti
    stats["targets_upd"] += tu
    stats["dt_ins"] += di
    stats["dt_upd"] += du
  session.commit()
  return stats


def ingest_opentargets(session: Session, *, offline_payloads: dict[str, Any] | None = None) -> dict:
  targets = session.scalars(select(Target).where(Target.ensembl_id.is_not(None))).all()
  stats = {"targets": 0, "pathways_ins": 0, "pathways_upd": 0, "links_ins": 0, "links_upd": 0}
  offline_mode = offline_payloads is not None
  offline = offline_payloads or {}
  for t in targets:
    assert t.ensembl_id
    stats["targets"] += 1
    if offline_mode:
      pathways = offline.get(t.ensembl_id, [])
    else:
      pathways = None
    prow, lrow = opentargets.build_pathway_rows(
      target_id=t.target_id,
      ensembl_id=t.ensembl_id,
      pathways=pathways,
    )
    pi, pu = loaders.upsert_pathways(session, prow)
    li, lu = loaders.upsert_pathway_targets(session, lrow)
    stats["pathways_ins"] += pi
    stats["pathways_upd"] += pu
    stats["links_ins"] += li
    stats["links_upd"] += lu
  session.commit()
  return stats


def ingest_clinvar(session: Session, *, offline_payloads: dict[str, Any] | None = None) -> dict:
  stats = {"genes": 0, "variants_ins": 0, "variants_upd": 0}
  offline_mode = offline_payloads is not None
  offline = offline_payloads or {}
  for gene in clinvar.DEFAULT_GENES:
    stats["genes"] += 1
    if offline_mode:
      payload = offline.get(gene, {"ids": [], "summaries": {}})
      rows = clinvar.build_variant_rows_for_gene(
        gene,
        ids=payload.get("ids") or [],
        summaries=payload.get("summaries") or {},
      )
    else:
      rows = clinvar.build_variant_rows_for_gene(gene, retmax=8)
    vi, vu = loaders.upsert_variants(session, rows)
    stats["variants_ins"] += vi
    stats["variants_upd"] += vu
  session.commit()
  return stats


def ingest_faers(session: Session, *, offline_payloads: dict[str, Any] | None = None) -> dict:
  settings = get_settings()
  drugs = session.scalars(select(Drug).where(Drug.is_mvp_seed.is_(True))).all()
  stats = {
    "drugs": 0,
    "ae_ins": 0,
    "ae_upd": 0,
    "cases_ins": 0,
    "cases_upd": 0,
    "events_ins": 0,
    "events_upd": 0,
  }
  offline_mode = offline_payloads is not None
  offline = offline_payloads or {}
  for drug in drugs:
    stats["drugs"] += 1
    name = drug.preferred_name
    if offline_mode:
      events = offline.get(name, [])
    else:
      events = faers.fetch_faers_for_drug(name)
      faers.snapshot_raw(name, events, settings.raw_data_dir)
    ae_rows, case_rows, link_rows = faers.build_faers_rows(
      drug_id=drug.drug_id,
      drug_name=name,
      events=events,
    )
    ai, au = loaders.upsert_ae_terms(session, ae_rows)
    pt_to_id = {a["pt_string"]: a["ae_term_id"] for a in ae_rows}
    clean_links = []
    for link in link_rows:
      pt = link.pop("pt_string", None)
      if pt and pt in pt_to_id:
        link["ae_term_id"] = pt_to_id[pt]
      clean_links.append(link)
    ci, cu = loaders.upsert_pv_cases(session, case_rows)
    session.flush()
    ei, eu = loaders.upsert_pv_drug_events(session, clean_links)
    xwalks = [
      {
        "entity_type": "ae",
        "from_system": "openfda_pt",
        "from_id": a["pt_string"],
        "to_system": "openfda_pt",
        "to_id": a["pt_string"],
        "confidence": 1.0,
      }
      for a in ae_rows
    ]
    loaders.upsert_crosswalks(session, xwalks)
    stats["ae_ins"] += ai
    stats["ae_upd"] += au
    stats["cases_ins"] += ci
    stats["cases_upd"] += cu
    stats["events_ins"] += ei
    stats["events_upd"] += eu
    # Append-only stream ledger (one summary event per drug batch)
    try:
      from stream.ledger import append_event

      append_event(
        session,
        source="openfda_faers",
        entity_key=f"faers_batch:{drug.drug_id}:{len(events)}",
        payload={
          "drug_id": drug.drug_id,
          "drug_name": name,
          "n_events": len(events),
          "cases_ins": ci,
          "events_ins": ei,
        },
        event_type="faers_batch",
        drug_id=drug.drug_id,
        summary=f"FAERS batch · {name} · {len(events)} reports",
        broadcast=False,  # offline pipeline — no WS loop
      )
    except Exception:  # noqa: BLE001 — ledger must not break Phase 1
      pass
  session.commit()
  return stats


def run_phase1(
  session: Session,
  *,
  steps: list[str] | None = None,
  offline_dir: Path | None = None,
) -> dict[str, Any]:
  wanted = steps or [
    "chembl",
    "opentargets",
    "clinvar",
    "faers",
    "lincs",
    "ctgov",
    "literature",
    "sider",
    "onsides",
    "opentargets_pv",
    "openfda_spl",
    "orange_book",
    "bindingdb",
    "tox21",
    "depmap",
    "eudravigilance",
    "meddra_codes",
    "meddra_hierarchy",
    "ictrp_ctri",
    "synthea",
  ]
  offline_mode = offline_dir is not None
  offline: dict[str, Any] = {}
  if offline_mode:
    assert offline_dir is not None
    load_names = set(wanted) | {"biodex"}
    for name in load_names:
      path = offline_dir / f"{name}.json"
      offline[name] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

  summary: dict[str, Any] = {"steps": {}, "mode": "offline" if offline_mode else "live"}
  if "chembl" in wanted:
    summary["steps"]["chembl"] = ingest_chembl(
      session, offline_payloads=offline.get("chembl") if offline_mode else None
    )
  if "opentargets" in wanted:
    summary["steps"]["opentargets"] = ingest_opentargets(
      session, offline_payloads=offline.get("opentargets") if offline_mode else None
    )
  if "clinvar" in wanted:
    summary["steps"]["clinvar"] = ingest_clinvar(
      session, offline_payloads=offline.get("clinvar") if offline_mode else None
    )
  if "faers" in wanted:
    summary["steps"]["faers"] = ingest_faers(
      session, offline_payloads=offline.get("faers") if offline_mode else None
    )
  if "lincs" in wanted:
    from ingest.lincs import ingest_lincs

    payload = offline.get("lincs") if offline_mode else {}
    summary["steps"]["lincs"] = ingest_lincs(session, payload or {})
  if "ctgov" in wanted:
    from ingest.ctgov_ae import ingest_ctgov

    payload = offline.get("ctgov") if offline_mode else {}
    summary["steps"]["ctgov"] = ingest_ctgov(session, payload or {})
  if "literature" in wanted:
    from ingest.literature import ingest_literature

    payload: dict[str, Any] = dict(offline.get("literature") or {}) if offline_mode else {}
    # merge BioDEX / Kidsides-style literature fixtures into the same evidence table
    biodex = offline.get("biodex") if offline_mode else {}
    for drug_id, rows in (biodex or {}).items():
      payload.setdefault(drug_id, []).extend(rows or [])
    summary["steps"]["literature"] = ingest_literature(session, payload or {})
  if "sider" in wanted:
    from ingest.literature import ingest_sider

    payload = offline.get("sider") if offline_mode else {}
    summary["steps"]["sider"] = ingest_sider(session, payload or {})
  if "onsides" in wanted:
    from ingest.literature import ingest_onsides

    payload = offline.get("onsides") if offline_mode else {}
    summary["steps"]["onsides"] = ingest_onsides(session, payload or {})
  if "opentargets_pv" in wanted:
    from ingest.literature import ingest_opentargets_pv

    payload = offline.get("opentargets_pv") if offline_mode else {}
    summary["steps"]["opentargets_pv"] = ingest_opentargets_pv(session, payload or {})
  if "openfda_spl" in wanted:
    from ingest.literature import ingest_openfda_spl

    payload = offline.get("openfda_spl") if offline_mode else {}
    summary["steps"]["openfda_spl"] = ingest_openfda_spl(session, payload or {})
  if "orange_book" in wanted:
    from ingest.orange_book import ingest_orange_book

    payload = offline.get("orange_book") if offline_mode else {}
    summary["steps"]["orange_book"] = ingest_orange_book(session, payload or {})
  if "bindingdb" in wanted:
    from ingest.bindingdb_tox import ingest_bindingdb

    payload = offline.get("bindingdb") if offline_mode else {}
    summary["steps"]["bindingdb"] = ingest_bindingdb(session, payload or {})
  if "tox21" in wanted:
    from ingest.bindingdb_tox import ingest_tox21

    payload = offline.get("tox21") if offline_mode else {}
    summary["steps"]["tox21"] = ingest_tox21(session, payload or {})
  if "depmap" in wanted:
    from ingest.bindingdb_tox import ingest_depmap

    payload = offline.get("depmap") if offline_mode else {}
    summary["steps"]["depmap"] = ingest_depmap(session, payload or {})
  if "eudravigilance" in wanted:
    from ingest.eudra import ingest_eudravigilance

    payload = offline.get("eudravigilance") if offline_mode else {}
    summary["steps"]["eudravigilance"] = ingest_eudravigilance(session, payload or {})
  if "meddra_codes" in wanted:
    from ingest.eudra import ingest_meddra_codes

    payload = offline.get("meddra_codes") if offline_mode else {}
    summary["steps"]["meddra_codes"] = ingest_meddra_codes(session, payload or {})
  if "meddra_hierarchy" in wanted:
    from ingest.clinical_layer import ingest_meddra_hierarchy

    payload = offline.get("meddra_hierarchy") if offline_mode else {}
    summary["steps"]["meddra_hierarchy"] = ingest_meddra_hierarchy(session, payload or {})
  if "ictrp_ctri" in wanted:
    from ingest.clinical_layer import ingest_ictrp_ctri

    payload = offline.get("ictrp_ctri") if offline_mode else {}
    summary["steps"]["ictrp_ctri"] = ingest_ictrp_ctri(session, payload or {})
  if "synthea" in wanted:
    from ingest.clinical_layer import ingest_synthea

    payload = offline.get("synthea") if offline_mode else {}
    summary["steps"]["synthea"] = ingest_synthea(session, payload or {})

  qc_path = write_qc_report(session)
  summary["qc_report"] = str(qc_path)
  return summary
