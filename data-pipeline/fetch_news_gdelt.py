"""Fetch commodity news headlines from GDELT (free, no key) into the `news`
table. Copyright-safe: we store only title, url, source, published date (GDELT's
article endpoint returns no article text, so snippet stays null). One article
matching several commodities is stored once with multiple tags.

    python fetch_news_gdelt.py                # last 7 days
    python fetch_news_gdelt.py --timespan 3d  # custom window

SCHEDULING (not set up this session): run every 15-30 min via cron, e.g.
    */20 * * * * cd <repo>/data-pipeline && python3 fetch_news_gdelt.py --timespan 1d
The UNIQUE(url) upsert makes repeated runs idempotent (refresh, no duplicates).
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time

from gdeltdoc import Filters, GdeltDoc

import news_relevance
import store as db

# Retry/pacing budget — tunable via env so CI can fail fast on GDELT throttling
# while local runs stay patient. Defaults preserve the original behaviour.
MAX_RETRIES = int(os.environ.get("GDELT_MAX_RETRIES", "5"))
RETRY_BASE = int(os.environ.get("GDELT_RETRY_BASE", "8"))
QUERY_SLEEP = int(os.environ.get("GDELT_QUERY_SLEEP", "10"))

# Our tracked commodities -> GDELT search terms. A bare word ("nickel") matches
# any context — "satin nickel" cabinet knobs, a phone's "graphite" colour, the
# place "Bukit Bintang" for tin. We couple each metal to market terms so GDELT
# only returns commodity-market news. A list is OR-ed as quoted phrases:
# ["nickel mine","nickel price"] -> ("nickel mine" OR "nickel price").
KEYWORDS = {
    "crude": ["crude oil", "oil price", "WTI crude", "Brent crude", "OPEC oil"],
    "lng": ["liquefied natural gas", "LNG cargo", "LNG terminal", "LNG export", "LNG import"],
    "copper": ["copper price", "copper mine", "copper smelter", "copper cathode", "copper ore"],
    "aluminium": ["aluminium price", "aluminium smelter", "aluminum production", "alumina", "bauxite"],
    "cobalt": ["cobalt price", "cobalt mine", "cobalt supply", "cobalt production", "cobalt ore"],
    "lithium": ["lithium price", "lithium mine", "lithium carbonate", "lithium battery", "lithium supply"],
    "nickel": ["nickel price", "nickel mine", "nickel ore", "nickel smelter", "nickel supply"],
    "rare_earths": ["rare earth", "rare earths", "rare earth magnet", "neodymium", "rare earth mine"],
    "zinc": ["zinc price", "zinc mine", "zinc smelter", "zinc ore", "zinc production"],
    "tin": ["tin price", "tin mine", "tin smelter", "tin ore", "tin production"],
    "manganese": ["manganese ore", "manganese price", "manganese mine", "manganese production"],
    "graphite": ["graphite price", "graphite mine", "graphite anode", "graphite production", "natural graphite"],
}
NUM_RECORDS = 60


def _seendate_to_iso(s: str) -> str | None:
    # GDELT seendate: 20260727T120000Z
    s = str(s)
    if len(s) >= 8 and s[:8].isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return None


def fetch_one(gd: GdeltDoc, commodity: str, kw: str, timespan: str) -> list[dict]:
    f = Filters(keyword=kw, timespan=timespan, num_records=NUM_RECORDS,
                language="English")
    for attempt in range(MAX_RETRIES):
        try:
            arts = gd.article_search(f)
            break
        except Exception as e:  # gdeltdoc.RateLimitError etc.
            wait = RETRY_BASE * (attempt + 1)
            print(f"    {type(e).__name__} on {commodity}, retry in {wait}s",
                  file=sys.stderr)
            time.sleep(wait)
    else:
        return []
    if arts is None or not len(arts):
        return []
    out = []
    for _, r in arts.iterrows():
        url = r.get("url")
        if not url:
            continue
        img = r.get("socialimage")               # article's own OG/social image
        img = img if isinstance(img, str) and img.strip() else None
        out.append({
            "title": r.get("title"), "url": url, "source": r.get("domain"),
            "published_date": _seendate_to_iso(r.get("seendate")),
            "image": img, "commodity": commodity,
        })
    print(f"  {commodity:12} ('{kw}'): {len(out)} articles")
    return out


def run(timespan: str) -> dict:
    gd = GdeltDoc()
    # Dedupe by url; collect all commodity tags per article.
    merged: dict[str, dict] = {}
    for commodity, kw in KEYWORDS.items():
        for a in fetch_one(gd, commodity, kw, timespan):
            m = merged.setdefault(a["url"], {**a, "tags": set()})
            m["tags"].add(commodity)
        time.sleep(QUERY_SLEEP)  # space queries — GDELT rate-limits bursts hard

    import json as _json
    rows = []
    for u, m in merged.items():
        if not m["title"]:
            continue
        # Editorial relevance guard at ingestion (the frontend has no build-time
        # filter anymore) — keep only market-relevant tags, drop off-topic items.
        keep = news_relevance.relevant_tags(m["title"], sorted(m["tags"]))
        if not keep:
            continue
        rows.append({
            "id": hashlib.md5(u.encode()).hexdigest(), "title": m["title"], "url": u,
            "source": m["source"], "published_date": m["published_date"],
            "snippet": None, "commodities_tags": _json.dumps(keep),
            "image": m.get("image"),
        })

    conn = db.get_connection()
    db.init_db(conn)
    written = db.upsert_news(conn, rows)
    pruned = db.prune_news(conn, 30) if hasattr(db, "prune_news") else 0
    conn.close()
    return {"articles": written, "pruned": pruned, "queries": len(KEYWORDS)}


def main() -> None:
    p = argparse.ArgumentParser(description="Fetch commodity news from GDELT.")
    p.add_argument("--timespan", default="7d", help="e.g. 7d, 3d, 1d, 12h")
    args = p.parse_args()
    print(f"Fetching news for {len(KEYWORDS)} commodities (timespan {args.timespan}):")
    rep = run(args.timespan)
    print(f"\nGDELT: {rep['articles']} unique articles written")


if __name__ == "__main__":
    main()
