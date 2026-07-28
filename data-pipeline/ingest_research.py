"""Ingest the Haiku-researched flagship producer lists (data/research/*.json)
into the facility table as source='Research' — the real top producers with
operator, production volume + year and coordinates (Africa included).

Photos: matched by site name against the Wikidata facilities already fetched
(their P18 Commons image), so well-known sites keep a presentation photo.

    python ingest_research.py
"""
from __future__ import annotations

import json

import config
import db

RESEARCH_DIR = config.DATA_DIR / "research"


def run() -> dict:
    conn = db.get_connection()
    db.init_db(conn)
    # Wikidata name -> photo, per commodity, for photo matching.
    wiki = {}
    for r in conn.execute("SELECT commodity, name, photo_url FROM facility "
                          "WHERE source='Wikidata' AND photo_url IS NOT NULL"):
        wiki.setdefault(r["commodity"], []).append((r["name"], r["photo_url"]))

    def match_photo(commodity, name):
        for wname, url in wiki.get(commodity, []):
            a, b = name.lower(), wname.lower()
            if a in b or b in a or a.split()[0] == b.split()[0]:
                return url
        return None

    report, total, photos = {}, 0, 0
    for path in sorted(RESEARCH_DIR.glob("*.json")):
        commodity = path.stem
        sites = json.loads(path.read_text())
        rows = []
        for s in sites:
            if s.get("lat") is None or s.get("lon") is None:
                continue
            photo = match_photo(commodity, s["name"])
            rows.append({
                "id": s["name"] + "#" + commodity, "name": s["name"],
                "type": "mine", "country_iso": s.get("country_iso3"),
                "lat": s["lat"], "lon": s["lon"], "commodity": commodity,
                "operator_company": s.get("operator"),
                "production_volume": s.get("production_tonnes"),
                "production_year": s.get("year"), "unit": "t", "capacity": None,
                "status": "operating", "start_date": None,
                "photo_url": photo, "photo_source": "Wikimedia Commons" if photo else None,
                "source": "Research",
            })
        db.upsert_facilities(conn, rows)
        p = sum(1 for r in rows if r["photo_url"])
        report[commodity] = {"sites": len(rows), "photos": p}
        total += len(rows); photos += p
    conn.close()
    report["_total"] = {"sites": total, "photos": photos}
    return report


def main() -> None:
    rep = run()
    print("Research facilities ingested:")
    for c, s in rep.items():
        if c == "_total":
            continue
        print(f"    {c:14}: {s['sites']:2} sites, {s['photos']:2} with photo")
    print(f"  total: {rep['_total']['sites']} sites, {rep['_total']['photos']} photos")


if __name__ == "__main__":
    main()
