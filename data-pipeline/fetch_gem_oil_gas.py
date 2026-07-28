"""Fetch oil/gas extraction fields + LNG terminals from Global Energy Monitor
into the `facility` table.

Sources (public GreenInfo viewer CSVs, no key, no form):
  - Global Oil & Gas Extraction Tracker  -> oil fields  (type='well')
  - Global Gas Infrastructure Tracker     -> LNG terminals (type='lng_terminal')

Only 'operating' assets. Top ~20 per commodity:
  - LNG terminals: ranked by capacity (MTPA) — real data.
  - Oil fields: the public data has NO field-level production volume, so we rank
    by the field's country oil production (EIA) and cap 3 per country for spread.
    This limitation is logged.

    python fetch_gem_oil_gas.py
"""
from __future__ import annotations

import csv
import sys
import urllib.request
from pathlib import Path

import config
import db
from country_maps import name_to_iso3

OIL_URL = ("https://greeninfo-network.github.io/"
           "global-oil-gas-extraction-tracker/data/data.csv")
LNG_URL = ("https://greeninfo-network.github.io/"
           "global-gas-infrastructure-tracker/data/data.csv")
RAW = config.DATA_DIR / "gem_raw"
TOP_N = 20


def _download(url: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    RAW.mkdir(parents=True, exist_ok=True)
    print(f"  ↓ {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "energy-map/1.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        dest.write_bytes(r.read())
    return dest


def _num(x):
    try:
        return float(str(x).replace(",", "")) if x not in (None, "", "TBD") else None
    except ValueError:
        return None


def _latlon(r, latk="lat", lonk="lng"):
    la, lo = _num(r.get(latk)), _num(r.get(lonk))
    if la is None or lo is None or not (-90 <= la <= 90) or not (-180 <= lo <= 180):
        return None, None
    return la, lo


def _country_oil_production(conn) -> dict:
    return {row["country_iso"]: row["volume"] or 0 for row in conn.execute(
        "SELECT country_iso, volume FROM production_latest "
        "WHERE commodity='crude_oil' AND source='EIA'")}


def fetch_oil(conn) -> int:
    rows = list(csv.DictReader(_download(OIL_URL, RAW / "goget.csv").open(encoding="utf-8-sig")))
    prod = _country_oil_production(conn)
    cand = []
    for r in rows:
        if "oil" not in (r.get("fuel_type") or "").lower():
            continue
        if (r.get("status") or "") != "operating":
            continue
        iso = name_to_iso3(r.get("country"))
        la, lo = _latlon(r)
        if not iso or la is None:
            continue
        cand.append({
            "id": r.get("url") or f"{r.get('project')}|{r.get('country')}",
            "name": r.get("project"), "type": "well", "country_iso": iso,
            "lat": la, "lon": lo, "commodity": "crude",
            "operator_company": r.get("operator") or None,
            "production_volume": None, "production_year": None, "unit": None,
            "capacity": None, "status": "operating",
            "start_date": (r.get("start_year") or None),
            "photo_url": None, "photo_source": None, "source": "GEM",
            "_rank": prod.get(iso, 0),
        })
    # Rank by country oil production; cap 3 per country for geographic spread.
    cand.sort(key=lambda x: -x["_rank"])
    picked, per = [], {}
    for f in cand:
        c = f["country_iso"]
        if per.get(c, 0) >= 3:
            continue
        per[c] = per.get(c, 0) + 1
        picked.append({k: v for k, v in f.items() if k != "_rank"})
        if len(picked) >= TOP_N:
            break
    print(f"  oil: {len(cand)} operating fields -> {len(picked)} kept "
          f"(ranked by country oil production; no field-level volume in GEM public data)")
    return db.upsert_facilities(conn, picked)


def fetch_lng(conn) -> int:
    rows = list(csv.DictReader(_download(LNG_URL, RAW / "ggit.csv").open(encoding="utf-8-sig")))
    cand = []
    for r in rows:
        t = r.get("type") or ""
        if "lng_terminals" not in t or (r.get("status") or "") != "operating":
            continue
        iso = name_to_iso3((r.get("countries") or "").split(",")[0])
        la, lo = _latlon(r)
        cap = _num(r.get("capacity"))
        if not iso or la is None:
            continue
        cand.append({
            "id": (r.get("url") or r.get("project") or "") + "#" + (r.get("unit") or ""),
            "name": r.get("project") + (f" ({r.get('unit')})" if r.get("unit") else ""),
            "type": "lng_terminal", "country_iso": iso, "lat": la, "lon": lo,
            "commodity": "lng", "operator_company": r.get("parent") or None,
            "production_volume": None, "production_year": None, "unit": r.get("capacity_units"),
            "capacity": cap, "status": "operating",
            "start_date": (r.get("start_year") or None),
            "photo_url": None, "photo_source": None, "source": "GEM",
            "_exp": "export" in t,
        })
    # Prefer export terminals (supply side), then rank by capacity.
    cand.sort(key=lambda x: (-int(x["_exp"]), -(x["capacity"] or 0)))
    picked = [{k: v for k, v in f.items() if k != "_exp"} for f in cand[:TOP_N]]
    print(f"  lng: {len(cand)} operating terminals -> {len(picked)} kept "
          f"(export first, ranked by capacity MTPA)")
    return db.upsert_facilities(conn, picked)


def main() -> None:
    conn = db.get_connection()
    db.init_db(conn)
    n = fetch_oil(conn) + fetch_lng(conn)
    conn.close()
    print(f"GEM: {n} facilities written to {config.DB_PATH}")


if __name__ == "__main__":
    main()
