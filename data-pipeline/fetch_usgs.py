"""Fetch world mine-production by country from the USGS Mineral Commodity
Summaries (MCS) Data Release into the existing `production` table.

Source (no API, no key): USGS MCS 2025 "World Production, Capacity, and
Reserves" CSV on ScienceBase. We keep MINE production only (the extraction
side), for the 10 Phase-2 metals, for 2023 (reported) and 2024 (estimated).

    python fetch_usgs.py                 # download if needed, then ingest
    python fetch_usgs.py --list          # print USGS commodity/type names & exit

Anomalies (a metal missing from the CSV, an unmapped country, a non-numeric
value) are logged, never silently dropped.
"""
from __future__ import annotations

import argparse
import csv
import sys
import urllib.request
from pathlib import Path

import config
import db
from country_maps import USGS_AGGREGATES, usgs_to_iso3

CSV_URL = ("https://www.sciencebase.gov/catalog/file/get/6798fd34d34ea8c18376e8ee"
           "?f=__disk__92%2Ff6%2F90%2F92f690853b1b1dc6a8000c1da24a7bbfd9f670d0")
CSV_PATH = config.DATA_DIR / "usgs_raw" / "MCS2025_World_Data.csv"

# metal slug -> (USGS COMMODITY name, TYPE prefix that marks MINE production)
METAL_USGS = {
    "copper":      ("Copper", "Mine production, recoverable copper content"),
    "aluminium":   ("Bauxite", "Mine production, bauxite"),
    "cobalt":      ("Cobalt", "Mine production"),
    "lithium":     ("Lithium", "Mine production, lithium content"),
    "nickel":      ("Nickel", "Mine production, nickel content"),
    "rare_earths": ("Rare earths", "Mine production, rare-earth-oxide equivalent"),
    "zinc":        ("Zinc", "Mine production, zinc content"),
    "tin":         ("Tin", "Mine production, tin content"),
    "manganese":   ("Manganese", "Mine production, manganese content"),
    "graphite":    ("Graphite", "Mine production"),
}


def _download() -> None:
    if CSV_PATH.exists() and CSV_PATH.stat().st_size > 0:
        return
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading USGS CSV -> {CSV_PATH}")
    req = urllib.request.Request(CSV_URL, headers={"User-Agent": "energy-map/1.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        CSV_PATH.write_bytes(r.read())


def _num(value: str) -> float | None:
    if value is None:
        return None
    v = value.strip().replace(",", "").replace("$", "")
    if v in ("", "W", "NA", "--", "—", "-", "(3)", "XX"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _rows() -> list[dict]:
    return list(csv.DictReader(CSV_PATH.open(encoding="utf-8-sig")))


def list_names() -> None:
    from collections import defaultdict
    seen = defaultdict(set)
    for r in _rows():
        seen[r["COMMODITY"].strip()].add(r["TYPE"].strip())
    for c in sorted(seen):
        print(f"{c!r}: {sorted(seen[c])}")


def ingest() -> dict:
    rows = _rows()
    # Column names carry stray spaces in the USGS file.
    hdr = {k.strip(): k for k in rows[0].keys()}
    col_2023 = next(k for k in rows[0] if k.strip() == "PROD_2023")
    col_2024 = next(k for k in rows[0] if k.strip().startswith("PROD_EST"))
    unit_col = hdr.get("UNIT_MEAS", "UNIT_MEAS")

    conn = db.get_connection()
    db.init_db(conn)

    report = {"per_metal": {}, "missing_metals": [], "unmapped": {},
              "aggregates_skipped": 0, "nonnumeric": 0}
    out_rows: list[dict] = []

    for metal, (commodity, type_prefix) in METAL_USGS.items():
        matched = [r for r in rows
                   if r["COMMODITY"].strip() == commodity
                   and r["TYPE"].strip().startswith(type_prefix)]
        if not matched:
            report["missing_metals"].append(f"{metal} ({commodity!r})")
            continue

        seen_country = set()
        countries = 0
        for r in matched:
            name = r["COUNTRY"].strip()
            iso = usgs_to_iso3(name)
            if iso is None:
                if name in USGS_AGGREGATES or "World" in name or name == "Other Countries":
                    report["aggregates_skipped"] += 1
                else:
                    report["unmapped"].setdefault(metal, set()).add(name)
                continue
            if iso in seen_country:      # dedupe (e.g. two cobalt TYPE variants)
                continue
            seen_country.add(iso)
            unit = (r.get(unit_col) or "metric tons").strip()
            for year, col in ((2023, col_2023), (2024, col_2024)):
                vol = _num(r.get(col))
                if vol is None:
                    report["nonnumeric"] += 1
                    continue
                out_rows.append({
                    "country_iso": iso, "commodity": metal, "year": year,
                    "volume": vol, "unit": unit, "source": "USGS",
                })
            countries += 1
        report["per_metal"][metal] = countries

    written = db.upsert_production(conn, out_rows)
    conn.close()
    report["rows_written"] = written
    return report


def print_report(rep: dict) -> None:
    print("\n=== USGS ingestion report ===")
    print(f"production rows written: {rep['rows_written']}")
    print("producing countries per metal (2023+2024 est.):")
    for metal, n in rep["per_metal"].items():
        print(f"    {metal:14}: {n} countries")
    if rep["missing_metals"]:
        print(f"! metals not found in CSV: {rep['missing_metals']}")
    if rep["unmapped"]:
        print("! unmapped country names (add to country_maps.USGS_NAME_TO_ISO3):")
        for metal, names in rep["unmapped"].items():
            print(f"    {metal}: {sorted(names)}")
    print(f"aggregate rows skipped: {rep['aggregates_skipped']} | "
          f"non-numeric values skipped: {rep['nonnumeric']}")


def main() -> None:
    p = argparse.ArgumentParser(description="Ingest USGS mine production.")
    p.add_argument("--list", action="store_true",
                   help="Print USGS commodity/type names and exit")
    args = p.parse_args()
    _download()
    if args.list:
        list_names()
        return
    print_report(ingest())


if __name__ == "__main__":
    main()
