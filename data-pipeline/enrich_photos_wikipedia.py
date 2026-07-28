"""Add a presentation photo to facilities that lack one, via the Wikipedia
pageimages API (fast, not rate-limited like WDQS). We only accept an image when
the matched Wikipedia page shares a word with the site name, to avoid wrong
photos.

    python enrich_photos_wikipedia.py
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request

import config
import db

API = "https://en.wikipedia.org/w/api.php"
STOP = {"mine", "the", "of", "and", "project", "co", "company", "field", "mining"}


def _search_image(query: str):
    p = {"action": "query", "generator": "search", "gsrsearch": query,
         "gsrlimit": 1, "prop": "pageimages", "piprop": "thumbnail",
         "pithumbsize": "500", "format": "json"}
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(p),
                                 headers={"User-Agent": "energy-map/1.0 (research; contact dev)"})
    for attempt in range(3):
        try:
            d = json.load(urllib.request.urlopen(req, timeout=30))
            for pg in d.get("query", {}).get("pages", {}).values():
                if "thumbnail" in pg:
                    return pg.get("title", ""), pg["thumbnail"]["source"]
            return None, None
        except Exception:
            time.sleep(1.5)
    return None, None


def _tokens(s: str):
    return {w for w in re.findall(r"[a-z0-9]+", s.lower())
            if w not in STOP and len(w) > 2}


def run() -> dict:
    conn = db.get_connection()
    db.init_db(conn)
    rows = conn.execute(
        "SELECT rowid, name, country_iso FROM facility "
        "WHERE (photo_url IS NULL OR photo_url='') AND source IN ('Research','GEM')"
    ).fetchall()
    found = 0
    for r in rows:
        want = _tokens(r["name"])
        img = None
        for query in (r["name"] + " mine", r["name"]):
            title, url = _search_image(query)
            if url and title and (_tokens(title) & want):
                img = url
                break
            time.sleep(0.6)
        if img:
            conn.execute("UPDATE facility SET photo_url=?, photo_source=? WHERE rowid=?",
                         (img, "Wikimedia Commons", r["rowid"]))
            conn.commit()      # persist immediately — resilient to interruption
            found += 1
    conn.close()
    return {"checked": len(rows), "photos_added": found}


def main() -> None:
    rep = run()
    print(f"Wikipedia photo enrichment: {rep['photos_added']} added "
          f"of {rep['checked']} sites checked")


if __name__ == "__main__":
    main()
