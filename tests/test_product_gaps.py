"""Product-gap closure tests: EDGAR, paged queue, health DB check, CSV columns."""

from __future__ import annotations

import csv
import io
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ingest.sec_edgar import (
    SPONSOR_TICKER,
    directory_coverage,
    edgar_browse_url,
    fixture_cik_for_ticker,
    sponsor_sec_entry,
)
from ingest.sources import sources_manifest
from qslrm_erd.db import reset_engine

RELEASE_DB = Path(__file__).parents[1] / "data" / "processed" / "qslrm.release.db"


def test_sec_edgar_directory_coverage():
    cov = directory_coverage()
    assert cov["sponsors"] == len(SPONSOR_TICKER) == 21
    assert cov["resolved"] >= 15
    assert cov["unlisted"] == 4  # Bayer, Boehringer, Roche/Genentech, Takeda
    pfizer = sponsor_sec_entry("Pfizer")
    assert pfizer["cik"] == 78003
    assert pfizer["edgar_url"] == edgar_browse_url(78003)
    assert sponsor_sec_entry("Boehringer Ingelheim")["source"] == "unlisted"
    assert fixture_cik_for_ticker("mkb") is None


def test_sec_edgar_in_sources_manifest():
    keys = {s["key"] for s in sources_manifest()}
    assert "sec_edgar" in keys


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    if not RELEASE_DB.exists():
        pytest.skip("release snapshot missing")
    db_path = tmp_path_factory.mktemp("release") / "qslrm.db"
    shutil.copyfile(RELEASE_DB, db_path)
    import os

    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    reset_engine()
    from api import main

    with TestClient(main.app) as c:
        yield c
    reset_engine()
    os.environ.pop("DATABASE_URL", None)


def test_health_reports_db(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["db_ok"] is True
    assert body["fused_pairs"] > 0


def test_queue_pagination_and_ranks(client):
    first = client.get("/v1/risk-scores", params={"limit": 5}).json()
    assert first["offset"] == 0
    assert len(first["items"]) == 5
    assert [i["rank"] for i in first["items"]] == [1, 2, 3, 4, 5]
    second = client.get("/v1/risk-scores", params={"limit": 5, "offset": 5}).json()
    assert second["offset"] == 5
    assert [i["rank"] for i in second["items"]] == [6, 7, 8, 9, 10]
    assert second["total"] == first["total"] > 5


def test_queue_filters_accepted(client):
    for params in (
        {"rising_only": True, "limit": 5},
        {"drug_class": "kinase_inhibitor", "limit": 5},
        {"q": "imatinib", "limit": 5},
    ):
        r = client.get("/v1/risk-scores", params=params)
        assert r.status_code == 200, params


def test_audit_csv_has_new_columns(client):
    r = client.get("/v1/audit", params={"format": "csv", "limit": 3})
    assert r.status_code == 200
    header = next(csv.reader(io.StringIO(r.text)))
    for col in ("sponsor_company", "brand_name", "drug_class", "delta_ror", "signal_velocity"):
        assert col in header


def test_catalog_has_sec_edgar(client):
    body = client.get("/v1/catalog").json()
    sec = body["domains"]["regulatory"]["sec_edgar"]
    assert sec["resolved"] >= 15
    assert body["queue"]["fused_pairs"] > 0


def _first_pair(client):
    items = client.get("/v1/risk-scores", params={"limit": 1}).json()["items"]
    assert items, "queue must be non-empty for draft-clause test"
    return items[0]["drug_id"], items[0]["ae_term_id"]


def test_protocol_draft_accepts_body_ids(client):
    drug_id, ae_term_id = _first_pair(client)
    r = client.post("/v1/protocol/draft", json={"drug_id": drug_id, "ae_term_id": ae_term_id})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["clause_text"]
    assert body["drug_id"] == drug_id
    assert body["ae_term_id"] == ae_term_id


def test_protocol_draft_accepts_query_ids(client):
    drug_id, ae_term_id = _first_pair(client)
    r = client.post("/v1/protocol/draft", params={"drug_id": drug_id, "ae_term_id": ae_term_id})
    assert r.status_code == 201, r.text
    assert r.json()["clause_text"]


def test_alphafold_fixture_mapping():
    from ingest.alphafold import (
        entry_page_url,
        gene_coverage,
        prediction_api_url,
        protein_entry,
        uniprot_for_gene,
    )

    assert uniprot_for_gene("CYP2D6") == "P10635"
    assert uniprot_for_gene("cyp2c19") == "P33261"
    assert uniprot_for_gene("nonsense_gene") is None
    assert prediction_api_url("P10635") == "https://alphafold.ebi.ac.uk/api/prediction/P10635"
    assert entry_page_url("P10635") == "https://alphafold.ebi.ac.uk/entry/P10635"
    entry = protein_entry("TPMT")
    assert entry["uniprot"] == "P51580"
    assert entry["source"] == "fixture"
    assert "prediction_summary" not in entry  # fixtures never invent coordinates
    assert protein_entry("nonsense_gene")["source"] == "unmapped"
    assert gene_coverage()["mapped"] == gene_coverage()["genes"] >= 10


def test_sec_edgar_facts_urls():
    from ingest.sec_edgar import companyfacts_url, sponsor_facts, submissions_url

    assert submissions_url(78003) == "https://data.sec.gov/submissions/CIK0000078003.json"
    assert companyfacts_url(78003).endswith("companyfacts/CIK0000078003.json")
    facts = sponsor_facts("Pfizer")
    assert facts["cik"] == 78003
    assert facts["submissions_url"] is not None
    assert facts["companyfacts_url"] is not None
    unlisted = sponsor_facts("Boehringer Ingelheim")
    assert unlisted["submissions_url"] is None


def test_manifest_covers_new_sources():
    keys = {s["key"] for s in sources_manifest()}
    for key in ("alphafold", "vigibase", "ctis_eu", "tggates", "msso_meddra", "sec_edgar"):
        assert key in keys
    gated = {s["key"]: s["auth"] for s in sources_manifest()}
    assert "not wired" in gated["vigibase"]
    assert "not wired" in gated["ctis_eu"]
    assert "not wired" in gated["msso_meddra"]


def test_health_degraded_without_tables(tmp_path):
    import os

    from sqlalchemy import create_engine

    from qslrm_erd.db import reset_engine
    from qslrm_erd.models import Base, EventLedger

    db_path = tmp_path / "empty.db"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    Base.metadata.create_all(engine, tables=[EventLedger.__table__])
    engine.dispose()
    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    reset_engine()
    try:
        from api import main

        with TestClient(main.app) as c:
            r = c.get("/health")
            assert r.status_code == 200
            body = r.json()
            assert body["status"] == "degraded"
            assert body["db_ok"] is False
            assert body["fused_pairs"] == 0
    finally:
        reset_engine()
        if old is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old


def test_stream_events_shape(client):
    body = client.get("/v1/stream/events", params={"limit": 5}).json()
    assert isinstance(body["items"], list)
    assert body["count"] == len(body["items"])


def test_stream_websocket_hello_and_ping(client):
    with client.websocket_connect("/v1/stream") as ws:
        hello = json.loads(ws.receive_text())
        assert hello["type"] == "hello"
        ws.send_text(json.dumps({"type": "ping"}))
        assert json.loads(ws.receive_text()) == {"type": "pong"}
