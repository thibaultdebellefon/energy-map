"""Editorial relevance guard for commodity news — applied at INGESTION now that
the frontend reads Supabase directly (no build-time filter step).

GDELT keyword matching lets noise through ("satin nickel" cabinet knobs, a
phone's "graphite" colour, place names). We keep a commodity tag on an article
only if its title names the commodity AND sits in a market context (or the name
is already market-specific, like "rare earth" or "crude oil").
"""
from __future__ import annotations

import re

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
SELF_SPECIFIC = {
    "crude": [r"crude oil", r"\bwti\b", r"brent", r"opec"],
    "lng": [r"\blng\b", r"liquefied natural gas"],
    "aluminium": [r"alumina", r"bauxite"],
    "rare_earths": [r"rare earth", r"neodymium", r"dysprosium", r"praseodymium", r"samarium"],
}
MARKET_TERMS = re.compile(
    r"\b("
    r"mine|mines|mining|miner|"
    r"price\w*|ore|ores|smelt\w*|suppl\w*|output|produc\w*|cargo|terminal|"
    r"export\w*|import\w*|futures|market\w*|refin\w*|cathode|carbonate|anode|"
    r"magnet\w*|demand|tonne\w*|shipment\w*|lme|opec|alumina|bauxite|"
    r"reserve\w*|deposit\w*|concentrate|offtake|feasibilit\w*|drill\w*|"
    r"explor\w*|stockpile\w*|inventor\w*|metal\w*|commodit\w*|barrel\w*|"
    r"pipeline|processing|grade|assay|resource\w*|mineral\w*|metallurg\w*|"
    r"tonnage|extraction|extract\w*|refinery"
    r")\b", re.I)


def relevant_tags(title: str, tags) -> list[str]:
    t = (title or "").lower()
    has_market = bool(MARKET_TERMS.search(t))
    keep = []
    for tag in (tags or []):
        base = BASE_WORDS.get(tag, [re.escape(tag)])
        if not any(re.search(p, t) for p in base):
            continue
        specific = SELF_SPECIFIC.get(tag)
        if (specific and any(re.search(p, t) for p in specific)) or has_market:
            keep.append(tag)
    return keep
