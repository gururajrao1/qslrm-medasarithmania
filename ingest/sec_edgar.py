"""SEC EDGAR sponsor resolution (fixture-backed with live lookup).

GAP_MATRIX lists "SEC EDGAR CIK / 10-K" as MISSING. This module closes the
read side of that gap: every MVP sponsor resolves to a CIK + EDGAR browse URL
so regulatory triage can link a drug–ADR pair to the applicant's filings.

Two paths:
- live: https://www.sec.gov/files/company_tickers.json (no auth) maps
  ticker -> CIK; companyfacts JSON gives R&D concepts on demand.
- offline: SPONSOR_TICKER + FIXTURE_CIK fixtures so tests and the catalog
  work without network.

Foreign/private sponsors with no EDGAR filer record (e.g. Boehringer
Ingelheim, Roche / Genentech as listed) resolve to None with
source="unlisted" instead of a fabricated CIK.
"""

from __future__ import annotations

from typing import Any

# Sponsor display name (as in qslrm_erd.seeds.kinase_mvp.SPONSOR_DIRECTORY)
# -> US-listed ticker. None = no EDGAR filer expected.
SPONSOR_TICKER: dict[str, str | None] = {
    "AbbVie": "ABBV",
    "Amgen": "AMGN",
    "AstraZeneca": "AZN",
    "Bayer": None,  # foreign filer, no reliable CIK fixture
    "Biogen": "BIIB",
    "BioNTech": "BNTX",
    "Boehringer Ingelheim": None,  # privately held
    "Bristol Myers Squibb": "BMY",
    "Eli Lilly": "LLY",
    "Gilead Sciences": "GILD",
    "GSK (GlaxoSmithKline)": "GSK",
    "Johnson & Johnson (Janssen)": "JNJ",
    "Merck & Co. (MSD)": "MRK",
    "Moderna": "MRNA",
    "Novartis": "NVS",
    "Pfizer": "PFE",
    "Regeneron": "REGN",
    "Roche / Genentech": None,  # foreign filer, no reliable CIK fixture
    "Sanofi": "SNY",
    "Takeda": None,  # foreign filer, no reliable CIK fixture
    "Vertex Pharmaceuticals": "VRTX",
}

# Offline fixture CIKs for US filers (resolvable without network).
FIXTURE_CIK: dict[str, int] = {
    "ABBV": 1551152,
    "AMGN": 318154,
    "AZN": 901832,
    "BIIB": 875045,
    "BNTX": 1776985,
    "BMY": 14272,
    "LLY": 59478,
    "GILD": 882095,
    "GSK": 1131399,
    "JNJ": 200406,
    "MRK": 310158,
    "MRNA": 1682852,
    "NVS": 1114448,
    "PFE": 78003,
    "REGN": 872589,
    "SNY": 1121404,
    "VRTX": 875320,
}

EDGAR_TICKER_URL = "https://www.sec.gov/files/company_tickers.json"
# data.sec.gov JSON APIs need a descriptive User-Agent header per SEC policy.
EDGAR_UA = {"User-Agent": "QSLRM-MedasArithmania triage-research contact@example.com"}


def submissions_url(cik: int) -> str:
    """Live company filing-index JSON (data.sec.gov, User-Agent required)."""
    return f"https://data.sec.gov/submissions/CIK{cik:010d}.json"


def companyfacts_url(cik: int) -> str:
    """Live XBRL companyfacts JSON (R&D / cost concepts live here)."""
    return f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"


def fetch_live_submissions(cik: int) -> dict | None:
    """Live filing index. None on any failure (offline-safe)."""
    from ingest.http_util import get_json

    try:
        payload = get_json(submissions_url(cik), headers=EDGAR_UA)
    except Exception:  # noqa: BLE001 -- network failure means offline fallback
        return None
    return payload if isinstance(payload, dict) else None


def sponsor_facts(sponsor: str) -> dict:
    """sponsor_sec_entry + live-address facts (URLs only, no fabricated data)."""
    entry = sponsor_sec_entry(sponsor)
    cik = entry.get("cik")
    entry["submissions_url"] = submissions_url(cik) if cik else None
    entry["companyfacts_url"] = companyfacts_url(cik) if cik else None
    return entry


def edgar_browse_url(cik: int) -> str:
    """Stable EDGAR company filing index for a CIK."""
    return f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik:010d}"


def fixture_cik_for_ticker(ticker: str) -> int | None:
    """Offline CIK fixture (None when unknown)."""
    return FIXTURE_CIK.get(ticker.upper())


def resolve_live_cik(ticker: str) -> int | None:
    """Resolve ticker -> CIK via EDGAR company_tickers.json. None on failure."""
    from ingest.http_util import get_json

    try:
        payload = get_json(EDGAR_TICKER_URL)
        want = ticker.upper()
        rows = payload.values() if isinstance(payload, dict) else payload
        for row in rows:
            if str(row.get("ticker", "")).upper() == want:
                return int(row["cik_str"])
    except Exception:  # noqa: BLE001 -- network or schema failure means offline fallback
        return None
    return None


def sponsor_sec_entry(sponsor: str, *, live: bool = False) -> dict[str, Any]:
    """One sponsor -> {cik, edgar_url, source} dict for catalog/regulatory use."""
    ticker = SPONSOR_TICKER.get(sponsor)
    if ticker is None:
        return {"sponsor": sponsor, "ticker": None, "cik": None, "edgar_url": None, "source": "unlisted"}
    cik: int | None = None
    source = "fixture"
    if live:
        cik = resolve_live_cik(ticker)
        if cik is not None:
            source = "live_edgar"
    if cik is None:
        cik = fixture_cik_for_ticker(ticker)
    if cik is None:
        return {"sponsor": sponsor, "ticker": ticker, "cik": None, "edgar_url": None, "source": "unresolved"}
    return {
        "sponsor": sponsor,
        "ticker": ticker,
        "cik": cik,
        "edgar_url": edgar_browse_url(cik),
        "source": source,
    }


def directory_coverage(*, live: bool = False) -> dict[str, Any]:
    """Coverage summary over the whole sponsor directory."""
    entries = [sponsor_sec_entry(s, live=live) for s in SPONSOR_TICKER]
    resolved = sum(1 for e in entries if e["cik"] is not None)
    return {
        "sponsors": len(entries),
        "resolved": resolved,
        "unlisted": sum(1 for e in entries if e["source"] == "unlisted"),
        "entries": entries,
    }
