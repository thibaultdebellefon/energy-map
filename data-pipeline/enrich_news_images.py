"""Backfill article photos by scraping og:image from the publisher page.

RSS feeds often ship no image, but the articles themselves carry an Open Graph
photo. We fetch the most recent image-less stories (capped per run to stay
polite and fast) and store their og:image / twitter:image. Hotlinked, never
re-hosted — same policy as the rest of the newsroom.

    python enrich_news_images.py
"""
from __future__ import annotations

import re
import time
import urllib.request

import store as db

UA = {"User-Agent": "Mozilla/5.0 (compatible; VantageBot/1.0; +https://vantage)"}
MAX_PER_RUN = 70
OG = [
    re.compile(r'<meta[^>]+property=["\']og:image(?::url)?["\'][^>]+content=["\']([^"\']+)', re.I),
    re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image', re.I),
    re.compile(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)', re.I),
]


def _og_image(url: str) -> str | None:
    req = urllib.request.Request(url, headers=UA)
    html = urllib.request.urlopen(req, timeout=12).read(400_000).decode("utf-8", "ignore")
    for pat in OG:
        m = pat.search(html)
        if m and re.match(r"https?://", m.group(1)):
            return m.group(1).replace("&amp;", "&")
    return None


def run() -> dict:
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute(
        "select id, url from news where image is null "
        "and published_date >= current_date - 7 "
        "order by published_date desc nulls last limit %s", (MAX_PER_RUN,))
    todo = cur.fetchall()
    found = 0
    for nid, url in todo:
        try:
            img = _og_image(url)
        except Exception:       # noqa: BLE001 — dead host / timeout, just skip
            img = None
        if img:
            cur.execute("update news set image=%s where id=%s", (img, nid))
            found += 1
        time.sleep(0.3)
    conn.commit()
    conn.close()
    print(f"  scanned {len(todo)} image-less stories → {found} photos found")
    return {"scanned": len(todo), "found": found}


def main() -> None:
    print("Enriching news photos via og:image:")
    run()


if __name__ == "__main__":
    main()
