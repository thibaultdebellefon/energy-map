"""Enrich the `facility` table with flagship mine sites from Wikidata (free, no
key): operator, coordinates, country ISO3, inception year, and a Wikimedia
Commons PHOTO — ranked by notability (sitelinks) to surface the real giants
(Chuquicamata, Grasberg, Kamoa-Kakula, Bayan Obo…), including Africa.

    python fetch_wikidata_facilities.py

Wikidata's SPARQL endpoint is sometimes rate-limited (1 req/min during
outages); we back off and retry. Sites without operator/volume are left for the
Haiku enrichment pass.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request

import config
import db

ENDPOINT = "https://query.wikidata.org/sparql"
TOP_N = 15

# commodity key -> Wikidata QID of the produced material (P1056)
METAL_QID = {
    "copper": "Q753", "aluminium": "Q184871",   # bauxite ore
    "cobalt": "Q1090", "lithium": "Q568", "nickel": "Q744",
    "rare_earths": "Q189302", "zinc": "Q758", "tin": "Q1615",
    "manganese": "Q731", "graphite": "Q5309",
}

QUERY = """SELECT ?mine ?mineLabel ?iso3 ?operatorLabel ?coord ?img ?inception ?sl WHERE {{
  ?mine wdt:P1056 wd:{qid} .
  ?mine wdt:P625 ?coord .
  ?mine wikibase:sitelinks ?sl .
  OPTIONAL {{ ?mine wdt:P17 ?country. ?country wdt:P298 ?iso3. }}
  OPTIONAL {{ ?mine wdt:P137 ?operator. }}
  OPTIONAL {{ ?mine wdt:P18 ?img. }}
  OPTIONAL {{ ?mine wdt:P571 ?inception. }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}} ORDER BY DESC(?sl) LIMIT 50"""


def sparql(qid: str) -> list[dict]:
    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": QUERY.format(qid=qid), "format": "json"})
    req = urllib.request.Request(url, headers={
        "User-Agent": "energy-map/1.0 (research project; facility enrichment)",
        "Accept": "application/sparql-results+json"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)["results"]["bindings"]
        except urllib.error.HTTPError as e:
            wait = 65 if e.code == 429 else 10
            print(f"    HTTP {e.code}, waiting {wait}s (attempt {attempt + 1})", file=sys.stderr)
            time.sleep(wait)
        except Exception as e:  # noqa: BLE001
            print(f"    {type(e).__name__}, retry in 10s", file=sys.stderr)
            time.sleep(10)
    return []


def _coord(wkt: str):
    m = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)", wkt or "")
    return (float(m.group(2)), float(m.group(1))) if m else (None, None)  # lat, lon


def _year(dt: str):
    m = re.match(r"(-?\d{4})", dt or "")
    return m.group(1) if m else None


def run() -> dict:
    conn = db.get_connection()
    db.init_db(conn)
    report = {"per_metal": {}, "low": []}
    for metal, qid in METAL_QID.items():
        rows = sparql(qid)
        seen, out = set(), []
        for r in rows:
            mid = r["mine"]["value"].rsplit("/", 1)[-1]
            if mid in seen:
                continue
            seen.add(mid)
            lat, lon = _coord(r.get("coord", {}).get("value"))
            if lat is None:
                continue
            out.append({
                "id": mid + "#" + metal, "name": r.get("mineLabel", {}).get("value"),
                "type": "mine", "country_iso": r.get("iso3", {}).get("value"),
                "lat": lat, "lon": lon, "commodity": metal,
                "operator_company": r.get("operatorLabel", {}).get("value"),
                "production_volume": None, "production_year": None, "unit": None,
                "capacity": None, "status": "operating",
                "start_date": _year(r.get("inception", {}).get("value")),
                "photo_url": r.get("img", {}).get("value"),
                "photo_source": "Wikimedia Commons" if "img" in r else None,
                "source": "Wikidata",
            })
            if len(out) >= TOP_N:
                break
        db.upsert_facilities(conn, out)
        photos = sum(1 for f in out if f["photo_url"])
        report["per_metal"][metal] = {"kept": len(out), "photos": photos}
        if len(out) < 6:
            report["low"].append(metal)
        print(f"  {metal:14}: {len(out):2} sites, {photos:2} with photo")
        time.sleep(63)   # respect the 1 req/min limit during outages
    conn.close()
    return report


def main() -> None:
    print("Fetching flagship mines from Wikidata (rate-limited, be patient):")
    rep = run()
    if rep["low"]:
        print(f"\nThin on Wikidata (need Haiku fill): {rep['low']}")


if __name__ == "__main__":
    main()
