"""Export news + price history from SQLite to JSON for the News and Trading
frontend sections.

    python app/build_news_trading.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR.parent / "data-pipeline"))
import db  # noqa: E402

PUBLIC = APP_DIR / "public"

# Editorial relevance guard. GDELT keyword matching lets noise through — "satin
# nickel" cabinet knobs, a phone's "graphite" colour, place names. A Bloomberg /
# FT feed would never surface those. We keep a commodity tag on an article only
# if its title names the commodity AND sits in a market context (or the name is
# already market-specific, like "rare earth" or "crude oil"). Belt-and-suspenders
# with the tightened GDELT queries in fetch_news_gdelt.py.
BASE_WORDS = {
    "crude": [r"crude", r"\boil\b", r"\bwti\b", r"brent", r"opec"],
    "lng": [r"\blng\b", r"liquefied natural gas"],
    "copper": [r"copper"],
    "aluminium": [r"alumini?um", r"alumina", r"bauxite"],
    "cobalt": [r"cobalt"],
    "lithium": [r"lithium"],
    "nickel": [r"nickel"],
    "rare_earths": [r"rare earth", r"neodymium", r"dysprosium", r"praseodymium", r"samarium"],
    "zinc": [r"\bzinc\b"],
    "tin": [r"\btin\b"],
    "manganese": [r"manganese"],
    "graphite": [r"graphite"],
}
# Names that already imply the commodity market on their own (no extra context
# term required).
SELF_SPECIFIC = {
    "crude": [r"crude oil", r"\bwti\b", r"brent", r"opec"],
    "lng": [r"\blng\b", r"liquefied natural gas"],
    "aluminium": [r"alumina", r"bauxite"],
    "rare_earths": [r"rare earth", r"neodymium", r"dysprosium", r"praseodymium", r"samarium"],
}
MARKET_TERMS = re.compile(
    r"\b("
    r"mine|mines|mining|miner|mining|"
    r"price\w*|ore|ores|smelt\w*|suppl\w*|output|produc\w*|cargo|terminal|"
    r"export\w*|import\w*|futures|market\w*|refin\w*|cathode|carbonate|anode|"
    r"magnet\w*|demand|tonne\w*|shipment\w*|lme|opec|alumina|bauxite|"
    r"reserve\w*|deposit\w*|concentrate|offtake|feasibilit\w*|drill\w*|"
    r"explor\w*|stockpile\w*|inventor\w*|metal\w*|commodit\w*|barrel\w*|"
    r"pipeline|processing|grade|assay|resource\w*|mineral\w*|metallurg\w*|"
    r"tonnage|extraction|extract\w*|refinery"
    r")\b", re.I)


def _relevant_tags(title: str, tags: list[str]) -> list[str]:
    t = (title or "").lower()
    has_market = bool(MARKET_TERMS.search(t))
    keep = []
    for tag in tags:
        base = BASE_WORDS.get(tag, [re.escape(tag)])
        if not any(re.search(p, t) for p in base):
            continue  # title doesn't even name the commodity
        specific = SELF_SPECIFIC.get(tag)
        if (specific and any(re.search(p, t) for p in specific)) or has_market:
            keep.append(tag)
    return keep


def main() -> None:
    conn = db.get_connection()
    db.init_db(conn)

    news = []
    for r in conn.execute(
        "SELECT title, url, source, published_date, commodities_tags FROM news "
        "ORDER BY published_date DESC LIMIT 800"):
        tags = _relevant_tags(r["title"], json.loads(r["commodities_tags"] or "[]"))
        if not tags:
            continue  # off-topic for every tag it carried — drop it
        news.append({
            "title": r["title"], "url": r["url"], "source": r["source"],
            "date": r["published_date"], "tags": tags,
        })
    news = news[:500]
    (PUBLIC / "news.json").write_text(json.dumps({"articles": news}, separators=(",", ":")))

    # Source per commodity. Prefer Alpha Vantage ONLY where it tracks the same
    # product as FRED and adds value (crude: identical WTI, longer daily
    # history). NOT for lng: AV's NATURAL_GAS is US Henry Hub (~$2.8/MMBtu),
    # a different market from FRED's Asia LNG landed price (~$17/MMBtu) that the
    # "LNG (Asia)" label describes. Metals: AV == FRED, keep FRED for one source.
    AV_PREFER = {"crude"}
    from collections import defaultdict
    raw = defaultdict(lambda: {"FRED": [], "AlphaVantage": []})
    unit_by = defaultdict(dict)
    for r in conn.execute(
        "SELECT commodity, date, price, unit, source FROM price_history "
        "ORDER BY commodity, date"):
        raw[r["commodity"]][r["source"]].append([r["date"], round(r["price"], 2)])
        unit_by[r["commodity"]][r["source"]] = r["unit"]
    prices, units, srcs = {}, {}, {}
    for c, by in raw.items():
        src = "AlphaVantage" if (c in AV_PREFER and by["AlphaVantage"]) else "FRED"
        if not by[src]:  # fall back if the preferred source is empty
            src = "AlphaVantage" if by["AlphaVantage"] else "FRED"
        prices[c] = by[src]
        units[c] = unit_by[c].get(src)
        srcs[c] = src
    (PUBLIC / "prices.json").write_text(
        json.dumps({"series": prices, "units": units, "sources": srcs},
                   separators=(",", ":")))
    conn.close()

    print(f"  ✓ news.json — {len(news)} articles")
    print(f"  ✓ prices.json — {len(prices)} commodities "
          f"({sum(len(v) for v in prices.values())} points)")


if __name__ == "__main__":
    main()
