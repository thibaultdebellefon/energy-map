"""Editorial rubric classifier for commodity-sector news.

Every article is filed under exactly one rubric so the news page can present
thematic sections instead of a flat commodity filter:

    geopolitics — sanctions, OPEC policy, war/supply risk, export bans, chokepoints
    contracts   — deals signed, contracts awarded, offtake, M&A, project FIDs
    company     — earnings, results, guidance, a company-specific economic scoop
    markets     — price moves, supply/demand, inventories (the market pulse)
    general     — sector news that fits none of the above (the catch-all)

Classification is rule-based (free, deterministic, no LLM cost): we score each
rubric by keyword hits on the title (weighted) + summary, and let strong source
signals — an Alpha Vantage `topics`/ticker, or a project-desk RSS feed — act as
priors. Ties break by the editorial priority order below.
"""
from __future__ import annotations

import re

# Rubric priority when scores tie (earlier wins). Company/contracts are the most
# specific; general is the floor.
PRIORITY = ["company", "contracts", "geopolitics", "markets", "general"]

# Keyword patterns per rubric. Word-boundaried, lower-cased match on title+summary.
RULES: dict[str, list[str]] = {
    "geopolitics": [
        r"sanction", r"embargo", r"export ban", r"import ban", r"\bban on\b",
        r"price cap", r"tariff", r"opec\+?", r"\bwar\b", r"conflict", r"ceasefire",
        r"attack", r"strike[sd]?\b", r"drone", r"missile", r"houthi", r"red sea",
        r"blockad", r"seiz(e|ed|ure)", r"nationali[sz]", r"expropriat",
        r"strait of hormuz", r"suez", r"chokepoint", r"geopolit", r"retaliat",
        r"diplomat", r"sanctioned", r"militar", r"escalat", r"tension",
        r"\bcoup\b", r"election", r"\bsanctions?\b", r"waiver", r"trade war",
    ],
    "contracts": [
        r"sign(s|ed)?\b.{0,20}(deal|agreement|contract|mou|pact)",
        r"(deal|agreement|contract|offtake|supply deal|pact)\b.{0,20}sign",
        r"award(s|ed)?\b.{0,20}contract", r"contract\b.{0,20}award",
        r"wins? .{0,20}(contract|tender|order)", r"secures?\b.{0,20}(deal|contract|supply)",
        r"offtake", r"long-term (supply|contract)", r"\btender\b",
        r"final investment decision", r"\bfid\b", r"greenlight",
        r"acqui(re|res|red|sition)", r"\bmerger\b", r"\bto buy\b", r"buys? (stake|unit)",
        r"joint venture", r"\bjv\b", r"memorandum", r"partnership",
        r"stake in", r"\$\d+(\.\d+)?\s?(bn|billion|m|million)\b.{0,20}(deal|invest|project|acqui)",
        r"to build", r"to develop", r"breaks? ground",
    ],
    "company": [
        r"earnings", r"quarterly (results|profit)", r"\bq[1-4]\b .{0,10}(results|profit|earnings)",
        r"net (income|profit|loss)", r"\bprofit (rose|fell|jump|drop|beat|miss)",
        r"revenue", r"guidance", r"dividend", r"buyback", r"share buyback",
        r"reports? .{0,15}(profit|loss|earnings|results)", r"beats? estimates",
        r"misses? estimates", r"\bceo\b", r"layoff", r"job cuts", r"restructur",
        r"downgrade", r"upgrade", r"analyst", r"quarterly report", r"annual results",
    ],
    "markets": [
        r"\bprices?\b", r"rall(y|ies)", r"slump", r"surg(e|ed|es)", r"plunge",
        r"\brose\b", r"\bfell\b", r"\bfalls?\b", r"\brises?\b", r"jump(s|ed)?",
        r"\bfutures\b", r"benchmark", r"per barrel", r"per tonne", r"per ton",
        r"inventor(y|ies)", r"stockpile", r"supply glut", r"oversupply",
        r"demand", r"output cut", r"production cut", r"record high", r"record low",
        r"bull(ish)?", r"bear(ish)?", r"\bspot price", r"\bhits\b .{0,15}(high|low)",
    ],
}
_COMPILED = {r: [re.compile(p) for p in pats] for r, pats in RULES.items()}

# RSS feeds whose editorial focus is a strong prior for a rubric.
FEED_BIAS = {
    "rigzone": "contracts", "offshore-technology": "contracts",
    "worldoil": "contracts", "nsenergybusiness": "contracts",
    "aljazeera": "geopolitics",
}

# Alpha Vantage topic → rubric.
AV_TOPIC_RUBRIC = {
    "earnings": "company", "ipo": "company", "financial_markets": "markets",
    "mergers_and_acquisitions": "contracts", "economy_macro": "geopolitics",
    "economy_monetary": "markets", "energy_transportation": "markets",
}


def _score(text: str) -> dict[str, int]:
    scores = {r: 0 for r in RULES}
    for r, pats in _COMPILED.items():
        for p in pats:
            if p.search(text):
                scores[r] += 1
    return scores


def classify(title: str, summary: str = "", *, source_domain: str | None = None,
             av_topics: list[str] | None = None, has_ticker: bool = False) -> str:
    """Return the rubric for one article. Title matches count double."""
    title = (title or "").lower()
    summary = (summary or "").lower()
    scores = _score(title)
    for r, n in _score(title).items():
        scores[r] += n           # title weighted 2x
    for r, n in _score(summary).items():
        scores[r] += n

    # Strong priors from structured source signals.
    if av_topics:
        for t in av_topics:
            r = AV_TOPIC_RUBRIC.get(t)
            if r:
                scores[r] += 2
    if has_ticker:
        scores["company"] += 1
    if source_domain:
        for frag, r in FEED_BIAS.items():
            if frag in source_domain:
                scores[r] += 2
                break

    best = max(scores.values())
    if best == 0:
        return "general"
    # Tie-break by editorial priority.
    for r in PRIORITY:
        if scores[r] == best:
            return r
    return "general"


if __name__ == "__main__":   # quick smoke test
    samples = [
        ("Russia hit with fresh EU sanctions on oil exports", ""),
        ("Aramco signs $10 billion LNG supply deal with China", ""),
        ("ExxonMobil Q2 earnings beat estimates on higher output", ""),
        ("Copper prices rally to record high on supply glut fears", ""),
        ("New refinery opens in Nigeria", ""),
    ]
    for t, s in samples:
        print(f"  {classify(t, s):12} {t}")
