"""Ingest curated commodity-sector RSS feeds into the `news` table.

All sources are free and keyless. Each is a sector-specialised outlet, so every
item is on-topic; we tag the commodity where the title names one and file the
article under an editorial rubric (geopolitics / contracts / company / markets /
general). Copyright-safe: we keep only headline, link, source, date and a short
snippet — the article stays on the publisher's site.

    python fetch_news_rss.py
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import news_relevance
import news_rubrics
import store as db

UA = {"User-Agent": "Mozilla/5.0 (compatible; VantageNews/1.0; +https://vantage)"}
MAX_AGE_DAYS = 10

# (display source, feed url). All sector-specialised → everything is on-topic.
FEEDS = [
    ("EIA Today in Energy", "https://www.eia.gov/rss/todayinenergy.xml"),
    ("OilPrice", "https://oilprice.com/rss/main"),
    ("Rigzone", "https://www.rigzone.com/news/rss/rigzone_latest.aspx"),
    ("Mining.com", "https://www.mining.com/feed/"),
    ("World Oil", "https://www.worldoil.com/rss?feed=news"),
    ("Offshore Technology", "https://www.offshore-technology.com/feed/"),
    ("NS Energy", "https://www.nsenergybusiness.com/feed/"),
]
ALL_COMMODITIES = list(news_relevance.BASE_WORDS.keys())


def _clean(s: str | None) -> str:
    if not s:
        return ""
    s = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)          # strip HTML
    return html.unescape(s).strip()


def _first(patterns, block) -> str | None:
    for p in patterns:
        m = re.search(p, block, re.S | re.I)
        if m:
            return m.group(1).strip()
    return None


def _parse_date(block: str) -> str | None:
    raw = _first([r"<pubDate>(.*?)</pubDate>", r"<published>(.*?)</published>",
                  r"<updated>(.*?)</updated>", r"<dc:date>(.*?)</dc:date>"], block)
    if not raw:
        return None
    raw = _clean(raw)
    for parse in (lambda s: parsedate_to_datetime(s),
                  lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))):
        try:
            dt = parse(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).date().isoformat()
        except Exception:
            continue
    return None


def _image(block: str) -> str | None:
    # Typed image elements (media:content / thumbnail / enclosure) declare an
    # image, so trust the URL regardless of extension — many CDNs omit one.
    for pat in (r'<media:content[^>]+url="([^"]+)"',
                r'<media:thumbnail[^>]+url="([^"]+)"',
                r'<enclosure[^>]+url="([^"]+)"[^>]*type="image'):
        m = re.search(pat, block, re.I)
        if m and re.match(r"https?://", m.group(1)):
            return html.unescape(m.group(1))
    # Inline <img> anywhere in the item (incl. content:encoded).
    m = re.search(r'<img[^>]+src="([^"]+)"', block, re.I)
    if m and re.match(r"https?://", m.group(1)) and \
            re.search(r"\.(jpg|jpeg|png|webp)", m.group(1), re.I):
        return html.unescape(m.group(1))
    return None


def _items(raw: str) -> list[str]:
    blocks = re.findall(r"<item\b.*?</item>", raw, re.S | re.I)
    if not blocks:
        blocks = re.findall(r"<entry\b.*?</entry>", raw, re.S | re.I)
    return blocks


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")


def run() -> dict:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)).date().isoformat()
    rows, seen = [], set()
    for source, url in FEEDS:
        try:
            raw = _fetch(url)
        except Exception as e:  # noqa: BLE001
            print(f"  {source:22} FETCH FAILED: {e}")
            continue
        domain = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
        n = 0
        for block in _items(raw):
            title = _clean(_first([r"<title>(.*?)</title>"], block))
            link = _clean(_first([r"<link>(.*?)</link>",
                                  r'<link[^>]+href="([^"]+)"'], block))
            if not title or not link or link in seen:
                continue
            date = _parse_date(block)
            if date and date < cutoff:
                continue
            summary = _clean(_first([r"<description>(.*?)</description>",
                                     r"<summary>(.*?)</summary>",
                                     r"<content:encoded>(.*?)</content:encoded>"], block))[:400]
            tags = news_relevance.relevant_tags(title, ALL_COMMODITIES)
            rubric = news_rubrics.classify(title, summary, source_domain=domain)
            rows.append({
                "id": hashlib.md5(link.encode()).hexdigest(), "title": title,
                "url": link, "source": source, "published_date": date,
                "snippet": summary or None, "commodities_tags": json.dumps(tags),
                "image": _image(block), "rubric": rubric,
            })
            seen.add(link)
            n += 1
        print(f"  {source:22} {n:3} items")
    conn = db.get_connection()
    db.init_db(conn)
    written = db.upsert_news(conn, rows)
    pruned = db.prune_news(conn, 30) if hasattr(db, "prune_news") else 0
    conn.close()
    from collections import Counter
    print(f"  → {written} upserted, {pruned} pruned | rubrics {dict(Counter(r['rubric'] for r in rows))}")
    return {"articles": written, "pruned": pruned}


def main() -> None:
    print("Fetching curated commodity RSS feeds → Supabase:")
    run()


if __name__ == "__main__":
    main()
