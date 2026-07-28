"""Central configuration: paths, credentials, and API constants.

Credentials are read from a `.env` file at the repo root (gitignored) or from
real environment variables. We parse `.env` by hand to avoid an extra
dependency on python-dotenv.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Paths ------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
DB_PATH = DATA_DIR / "energy_map.db"


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader. Does not overwrite already-set env vars."""
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(REPO_ROOT / ".env")


def require_key(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(
            f"Missing {name}. Add it to {REPO_ROOT / '.env'} "
            f"(see .env.example) and retry."
        )
    return value


def optional_key(name: str) -> str:
    """Return the key or "" — for APIs with a limited anonymous tier."""
    return os.environ.get(name, "").strip()


# --- Commodities (Phase 1: crude oil + LNG only) ----------------------------
# HS codes drive Comtrade; commodity slugs drive EIA + our own schema.
HS_CODES = {
    "crude_oil": "2709",    # Petroleum oils, crude
    "lng": "271111",        # Natural gas, liquefied
}
COMMODITY_BY_HS = {v: k for k, v in HS_CODES.items()}

# --- Phase 2: 10 metals (ore + refined where both exist) --------------------
# HS codes verified against Comtrade includeDesc descriptions (2026-07-18).
# Slug -> {"ore": hs|None, "refined": hs|None}. Lithium refined = carbonate
# only (283691); hydroxide (282520) is NOT covered.
METAL_HS = {
    "copper":      {"ore": "2603", "refined": "7403"},
    "aluminium":   {"ore": "2606", "refined": "7601"},   # ore = bauxite
    "cobalt":      {"ore": "2605", "refined": "8105"},
    "lithium":     {"ore": None,   "refined": "283691"},
    "nickel":      {"ore": "2604", "refined": "7502"},
    "rare_earths": {"ore": None,   "refined": "280530"},  # + compounds 2846
    "rare_earths_compounds": {"ore": None, "refined": "2846"},
    "zinc":        {"ore": "2608", "refined": "7901"},
    "tin":         {"ore": "2609", "refined": "8001"},
    "manganese":   {"ore": "2602", "refined": "8111"},
    "graphite":    {"ore": "2504", "refined": None},
}
# Flat, de-duplicated list of metal HS codes for bulk Comtrade fetching.
METAL_HS_CODES = sorted({hs for m in METAL_HS.values()
                         for hs in m.values() if hs})

# Default reference year(s). 2026 per project brief — note that Comtrade/EIA
# annual data lags ~1 year, so 2026 will be empty until ~2027. The fetchers
# detect an empty result and suggest MOST_RECENT_COMPLETE_YEAR as a fallback.
DEFAULT_YEARS = [2026]
MOST_RECENT_COMPLETE_YEAR = 2023

# --- UN Comtrade API v1 -----------------------------------------------------
# Docs: https://comtradedeveloper.un.org/
# GET https://comtradeapi.un.org/data/v1/get/{typeCode}/{freqCode}/{clCode}
COMTRADE_BASE = "https://comtradeapi.un.org/data/v1/get"
COMTRADE_TYPE = "C"     # C = commodities
COMTRADE_FREQ = "A"     # A = annual
COMTRADE_CL = "HS"      # HS classification
COMTRADE_FLOW_EXPORT = "X"   # X = export (we want export flows reporter -> partner)
COMTRADE_ROW_CAP = 100_000   # per-call ceiling with a subscription key
COMTRADE_RATE_LIMIT_S = 1.0  # >= 1 request/second

# --- EIA API v2 -------------------------------------------------------------
# Docs: https://www.eia.gov/opendata/documentation.php
EIA_BASE = "https://api.eia.gov/v2"
EIA_PAGE_LENGTH = 5000  # max rows per page

# International route facets. These mirror the legacy INTL series ids:
#   crude:  INTL.57-1-<country>-TBPD.A  (product 57, activity 1 = production)
#   gas:    INTL.26-1-<country>-BCF.A   (product 26, activity 1 = production)
# If a query returns 0 rows, run `fetch_eia.py --discover` to print the live
# facet ids from the API metadata endpoint and adjust here.
EIA_INTL = {
    "crude_oil": {
        "route": "international",
        "product_id": "57",     # Crude oil incl. lease condensate
        "activity_id": "1",     # Production
        "unit": "TBPD",         # thousand barrels per day
    },
    "natural_gas": {
        "route": "international",
        "product_id": "26",     # Dry natural gas
        "activity_id": "1",     # Production
        "unit": "BCF",          # billion cubic feet
    },
}
