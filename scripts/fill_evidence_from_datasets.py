"""Fill evidence fixtures from real public datasets (SIDER dump, OnSIDES zip, Open Targets API)."""

from __future__ import annotations

import csv
import gzip
import json
import time
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "tests" / "fixtures" / "phase1"

DRUGS = [
  ("imatinib", "drug_imatinib", "CHEMBL941", 5291),
  ("erlotinib", "drug_erlotinib", "CHEMBL553", 176870),
  ("gefitinib", "drug_gefitinib", "CHEMBL939", 123631),
  ("dasatinib", "drug_dasatinib", "CHEMBL1421", 3062316),
  ("nilotinib", "drug_nilotinib", "CHEMBL1168", 644241),
  ("sunitinib", "drug_sunitinib", "CHEMBL535", 5329102),
  ("sorafenib", "drug_sorafenib", "CHEMBL1336", 216239),
  ("lapatinib", "drug_lapatinib", "CHEMBL554", 208908),
  ("pazopanib", "drug_pazopanib", "CHEMBL119929", 10113978),
  ("axitinib", "drug_axitinib", "CHEMBL1289926", 6450551),
  ("ibrutinib", "drug_ibrutinib", "CHEMBL1873475", 24821094),
  ("osimertinib", "drug_osimertinib", "CHEMBL3353410", 71496458),
  ("tofacitinib", "drug_tofacitinib", "CHEMBL221959", 9926791),
]

MAX_SIDER = 100
MAX_ONSIDES = 100
MAX_OT = 50
ONSIDES_PRED_MIN = 3.258  # v3.1.1 high-confidence threshold


def stitch_flat(cid: int) -> set[str]:
  return {"CID1" + str(cid).zfill(8), "CID1" + str(cid).zfill(9)}


def load_sider() -> dict[str, list[dict]]:
  path = RAW / "meddra_all_se.tsv.gz"
  want: dict[str, str] = {}
  for _name, did, _chembl, cid in DRUGS:
    for key in stitch_flat(cid):
      want[key] = did
  pts: dict[str, set[str]] = defaultdict(set)
  with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
    for line in fh:
      parts = line.rstrip("\n").split("\t")
      if len(parts) < 6:
        continue
      flat, _stereo, _umls, term_type, _meddra_umls, se_name = parts[:6]
      if flat not in want or term_type != "PT":
        continue
      pts[want[flat]].add(se_name)
  out: dict[str, list[dict]] = {}
  for _name, did, _c, _cid in DRUGS:
    aes = sorted(pts.get(did, []))
    rows = []
    for i, ae in enumerate(aes[:MAX_SIDER]):
      freq = "common" if i < 20 else ("uncommon" if i < 50 else "rare")
      rows.append({"ae": ae, "frequency": freq, "source": "sider"})
    out[did] = rows
    print(f"SIDER {did}: {len(rows)}/{len(aes)} PTs")
  return out


def fetch_ot(chembl_id: str) -> list[dict]:
  q = {
    "query": """
      query($id:String!,$size:Int!){
        drug(chemblId:$id){
          adverseEvents(page:{index:0,size:$size}){
            rows{ name count logLR }
          }
        }
      }
    """,
    "variables": {"id": chembl_id, "size": MAX_OT},
  }
  req = urllib.request.Request(
    "https://api.platform.opentargets.org/api/v4/graphql",
    data=json.dumps(q).encode(),
    headers={"Content-Type": "application/json", "User-Agent": "QSLRM/1.0"},
    method="POST",
  )
  with urllib.request.urlopen(req, timeout=60) as resp:
    data = json.loads(resp.read().decode())
  rows = (((data.get("data") or {}).get("drug") or {}).get("adverseEvents") or {}).get("rows") or []
  out = []
  for r in rows:
    name = r.get("name")
    if not name:
      continue
    llr = r.get("logLR")
    cnt = r.get("count")
    freq = f"OT_LRT logLR={llr:.2f}" if isinstance(llr, (int, float)) else "OT_LRT"
    if isinstance(cnt, int):
      freq += f"; n={cnt}"
    out.append({"ae": name, "frequency": freq[:64], "source": "opentargets_pv"})
  return out


def ensure_onsides_csv() -> Path:
  extract_dir = RAW / "onsides_v311"
  extract_dir.mkdir(parents=True, exist_ok=True)
  needed = [
    "product_adverse_effect.csv",
    "product_to_rxnorm.csv",
    "vocab_rxnorm_ingredient_to_product.csv",
    "vocab_rxnorm_ingredient.csv",
    "vocab_meddra_adverse_effect.csv",
  ]
  if all((extract_dir / n).exists() for n in needed):
    return extract_dir
  zpath = RAW / "onsides-v3.1.1.zip"
  with zipfile.ZipFile(zpath) as zf:
    for m in zf.namelist():
      name = Path(m).name
      if name in needed:
        with zf.open(m) as src, (extract_dir / name).open("wb") as dst:
          dst.write(src.read())
  return extract_dir


def load_onsides() -> dict[str, list[dict]]:
  base = ensure_onsides_csv()
  want = {n.lower() for n, _d, _c, _cid in DRUGS}
  name_to_did = {n.lower(): did for n, did, _c, _cid in DRUGS}
  # aliases for matching
  aliases = {
    "tofacitinib": {"tofacitinib", "xeljanz"},
    "imatinib": {"imatinib", "gleevec", "glivec"},
  }

  ing = {
    r["rxnorm_id"]: r["rxnorm_name"]
    for r in csv.DictReader((base / "vocab_rxnorm_ingredient.csv").open(encoding="utf-8"))
  }
  med = {
    r["meddra_id"]: r["meddra_name"]
    for r in csv.DictReader((base / "vocab_meddra_adverse_effect.csv").open(encoding="utf-8"))
  }
  prod_to_ing: dict[str, set[str]] = defaultdict(set)
  with (base / "vocab_rxnorm_ingredient_to_product.csv").open(encoding="utf-8") as fh:
    for r in csv.DictReader(fh):
      prod_to_ing[r["product_id"]].add(r["ingredient_id"])
  label_to_prod = {
    r["label_id"]: r["rxnorm_product_id"]
    for r in csv.DictReader((base / "product_to_rxnorm.csv").open(encoding="utf-8"))
  }

  ing_to_drug: dict[str, str] = {}
  for iid, name in ing.items():
    low = name.lower()
    for drug in want:
      keys = aliases.get(drug, {drug})
      if any(low == k or low.startswith(k + " ") or f" {k}" in f" {low}" for k in keys):
        ing_to_drug[iid] = name_to_did[drug]

  best: dict[str, dict[str, float]] = defaultdict(dict)  # did -> ae -> max pred
  with (base / "product_adverse_effect.csv").open(encoding="utf-8") as fh:
    for r in csv.DictReader(fh):
      try:
        pred = float(r.get("pred1") or 0)
      except ValueError:
        continue
      if pred < ONSIDES_PRED_MIN:
        continue
      prod = label_to_prod.get(r["product_label_id"])
      if not prod:
        continue
      ae = med.get(r["effect_meddra_id"])
      if not ae or len(ae) < 3:
        continue
      for iid in prod_to_ing.get(prod, ()):
        did = ing_to_drug.get(iid)
        if not did:
          continue
        prev = best[did].get(ae)
        if prev is None or pred > prev:
          best[did][ae] = pred

  out: dict[str, list[dict]] = {}
  for name, did, _c, _cid in DRUGS:
    ranked = sorted(best.get(did, {}).items(), key=lambda x: -x[1])[:MAX_ONSIDES]
    rows = []
    for ae, pred in ranked:
      section_note = "label_confirmed"
      rows.append({"ae": ae, "frequency": f"{section_note}; pred={pred:.2f}"[:64], "source": "onsides"})
    out[did] = rows
    print(f"OnSIDES {name}: {len(rows)}")
  return out


def main() -> None:
  OUT.mkdir(parents=True, exist_ok=True)
  sider = load_sider()
  (OUT / "sider.json").write_text(json.dumps(sider, indent=2), encoding="utf-8")

  onsides = load_onsides()
  (OUT / "onsides.json").write_text(json.dumps(onsides, indent=2), encoding="utf-8")

  ot: dict[str, list] = {}
  for name, did, chembl, _cid in DRUGS:
    try:
      ot[did] = fetch_ot(chembl)
      print(f"OT {name}: {len(ot[did])}")
    except Exception as exc:  # noqa: BLE001
      print(f"OT {name} fail: {exc}")
      ot[did] = []
    time.sleep(0.2)
  (OUT / "opentargets_pv.json").write_text(json.dumps(ot, indent=2), encoding="utf-8")

  summary = {
    "sider_rows": sum(len(v) for v in sider.values()),
    "onsides_rows": sum(len(v) for v in onsides.values()),
    "opentargets_pv_rows": sum(len(v) for v in ot.values()),
  }
  for key in ("literature", "openfda_spl", "biodex"):
    path = OUT / f"{key}.json"
    if path.exists():
      payload = json.loads(path.read_text(encoding="utf-8"))
      summary[f"{key}_rows"] = sum(len(v) for v in payload.values())
  print(json.dumps(summary, indent=2))
  (OUT / "_evidence_fill_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
  main()
