"""Pick candidate mine sites per metal from USGS MRDS into the `facility` table.

Source: USGS Mineral Resources Data System full CSV (public, no key). MRDS is
uneven and US-centric, so we RANK by data completeness and keep the top 20 per
metal as "flagship candidates" (operator / photo / dates enriched later):
  score = size (Large>Medium>Small) + dev_stat (Producer>Past Producer>…)
          + has discovery year + has production years.

    python fetch_mrds_candidates.py

Reports metals with too few reliable candidates — those need manual curation.
"""
from __future__ import annotations

import csv
import sys
import zipfile
from pathlib import Path

import config
import db
from country_maps import name_to_iso3

RAW = config.DATA_DIR / "mrds_raw"
ZIP_URL = "https://mrdata.usgs.gov/mrds/mrds-csv.zip"
TOP_N = 20
MIN_RELIABLE = 10   # below this we flag the metal for manual curation

# our metal slug -> keyword(s) matched against MRDS commodity fields
MRDS_METAL = {
    "copper": ("copper",), "aluminium": ("aluminum", "bauxite"),
    "cobalt": ("cobalt",), "lithium": ("lithium",), "nickel": ("nickel",),
    "rare_earths": ("rare earth", "rare-earth", "cerium", "yttrium"),
    "zinc": ("zinc",), "tin": ("tin",), "manganese": ("manganese",),
    "graphite": ("graphite",),
}
SIZE = {"L": 3, "M": 2, "S": 1}
DEV = {"Producer": 3, "Plant": 3, "Past Producer": 2, "Prospect": 1,
       "Occurrence": 0, "Unknown": 0}
STATUS = {"Producer": "operating", "Plant": "operating",
          "Past Producer": "closed", "Prospect": "development",
          "Occurrence": "development", "Unknown": "development"}


def _ensure_csv() -> Path:
    csv_path = RAW / "mrds.csv"
    if csv_path.exists() and csv_path.stat().st_size > 0:
        return csv_path
    RAW.mkdir(parents=True, exist_ok=True)
    zpath = RAW / "mrds.zip"
    if not zpath.exists():
        import urllib.request
        print(f"  ↓ {ZIP_URL}")
        req = urllib.request.Request(ZIP_URL, headers={"User-Agent": "energy-map/1.0"})
        with urllib.request.urlopen(req, timeout=180) as r:
            zpath.write_bytes(r.read())
    with zipfile.ZipFile(zpath) as z:
        z.extract("mrds.csv", RAW)
    return csv_path


def _num(x):
    try:
        return float(x) if x not in (None, "") else None
    except ValueError:
        return None


def run() -> dict:
    csv_path = _ensure_csv()
    cand = {m: [] for m in MRDS_METAL}

    with open(csv_path, encoding="utf-8", errors="replace") as f:
        for r in csv.DictReader(f):
            lat, lon = _num(r["latitude"]), _num(r["longitude"])
            if lat is None or lon is None:
                continue
            commods = " ".join(filter(None, (r["commod1"], r["commod2"], r["commod3"]))).lower()
            if not commods:
                continue
            iso = name_to_iso3(r["country"]) or ("USA" if not r["country"].strip() else None)
            if not iso:
                continue
            score = (SIZE.get(r["prod_size"], 0) + DEV.get(r["dev_stat"], 0)
                     + (1 if r["disc_yr"] else 0) + (1 if r["yr_lst_prd"] else 0))
            for metal, kws in MRDS_METAL.items():
                if any(k in commods for k in kws):
                    cand[metal].append((score, {
                        # commodity-specific id so a polymetallic site can appear
                        # under each metal it hosts.
                        "id": (r["url"] or r["dep_id"] or r["mrds_id"]) + "#" + metal,
                        "name": r["site_name"] or None, "type": "mine",
                        "country_iso": iso, "lat": lat, "lon": lon,
                        "commodity": metal, "operator_company": None,
                        "production_volume": None, "production_year": None,
                        "unit": None, "capacity": None,
                        "status": STATUS.get(r["dev_stat"], "development"),
                        "start_date": (r["disc_yr"] or None),
                        "photo_url": None, "photo_source": None,
                        "source": "USGS_MRDS",
                    }))

    report = {"per_metal": {}, "low_confidence": []}
    written = 0
    for metal, items in cand.items():
        items.sort(key=lambda x: -x[0])
        top = [d for _, d in items[:TOP_N]]
        # a "reliable" candidate has score >= 3 (sized or a (past) producer)
        reliable = sum(1 for s, _ in items if s >= 3)
        report["per_metal"][metal] = {"kept": len(top), "matches": len(items),
                                      "reliable": reliable}
        if reliable < MIN_RELIABLE:
            report["low_confidence"].append(metal)
        written += db.upsert_facilities(db_conn, top)
    report["written"] = written
    return report


def main() -> None:
    global db_conn
    db_conn = db.get_connection()
    db.init_db(db_conn)
    rep = run()
    db_conn.close()
    print("\n=== MRDS candidates ===")
    print(f"facilities written: {rep['written']}")
    for metal, s in rep["per_metal"].items():
        flag = "  ⚠ few reliable" if metal in rep["low_confidence"] else ""
        print(f"    {metal:14}: {s['kept']:2} kept / {s['matches']:5} matches / "
              f"{s['reliable']:4} reliable{flag}")
    if rep["low_confidence"]:
        print(f"\nMetals needing manual curation (MRDS too thin): "
              f"{rep['low_confidence']}")


if __name__ == "__main__":
    main()
