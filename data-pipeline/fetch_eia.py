"""Fetch annual production (crude oil + natural gas) from EIA API v2 into SQLite.

Usage:
    python fetch_eia.py --years 2023
    python fetch_eia.py --discover        # print live facet ids and exit

Writes into `production(country_iso, commodity, year, volume, unit, source)`.
Country normalisation to ISO3 happens later in normalize_countries.py; here we
store EIA's raw countryRegionId in country_iso.
"""
from __future__ import annotations

import argparse
import sys
import time

import requests

import config
import db


def _to_float(value) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def _get(path: str, params: dict) -> dict:
    url = f"{config.EIA_BASE}/{path}"
    delay = 2.0
    for attempt in range(1, 5):
        try:
            resp = requests.get(url, params=params, timeout=60)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise requests.HTTPError(f"HTTP {resp.status_code}")
            resp.raise_for_status()
            return resp.json().get("response", {})
        except (requests.RequestException, ValueError) as exc:
            if attempt == 4:
                raise SystemExit(f"EIA request failed: {exc}")
            print(f"  retry {attempt}/4 in {delay:.0f}s ({exc})", file=sys.stderr)
            time.sleep(delay)
            delay *= 2
    return {}


def discover(key: str) -> None:
    """Print available facets for each configured route to verify ids."""
    for commodity, cfg in config.EIA_INTL.items():
        print(f"\n=== {commodity} — route '{cfg['route']}' facets ===")
        meta = _get(cfg["route"], {"api_key": key})
        for facet in meta.get("facets", []):
            print(f"  facet: {facet.get('id')} — {facet.get('description')}")


def fetch_commodity(commodity: str, cfg: dict, years: list[int], key: str) -> list[dict]:
    """Page through EIA international data for one commodity."""
    rows: list[dict] = []
    offset = 0
    while True:
        params = {
            "api_key": key,
            "frequency": "annual",
            "data[0]": "value",
            "facets[productId][]": cfg["product_id"],
            "facets[activityId][]": cfg["activity_id"],
            "start": str(min(years)),
            "end": str(max(years)),
            "offset": str(offset),
            "length": str(config.EIA_PAGE_LENGTH),
        }
        resp = _get(f"{cfg['route']}/data", params)
        page = resp.get("data", [])
        for r in page:
            year = int(r.get("period"))
            if year not in years:
                continue
            # EIA returns the same product in several units (e.g. QBTU + TBPD);
            # keep only the target unit so country-year rows stay unique.
            if (r.get("unit") or "").upper() != cfg["unit"].upper():
                continue
            country = (r.get("countryRegionId") or "").upper().strip()
            if not country:
                continue
            rows.append(
                {
                    "country_iso": country,      # raw; normalised later
                    "commodity": commodity,
                    "year": year,
                    "volume": _to_float(r.get("value")),
                    "unit": r.get("unit") or cfg["unit"],
                    "source": "EIA",
                }
            )
        total = int(resp.get("total", 0))
        offset += config.EIA_PAGE_LENGTH
        if offset >= total or not page:
            break
        time.sleep(0.3)
    print(f"  {commodity}: {len(rows)} country-year rows")
    return rows


def run(years: list[int], commodities: list[str]) -> int:
    key = config.require_key("EIA_KEY")
    conn = db.get_connection()
    db.init_db(conn)

    total = 0
    for commodity in commodities:
        cfg = config.EIA_INTL[commodity]
        rows = fetch_commodity(commodity, cfg, years, key)
        total += db.upsert_production(conn, rows)

    conn.close()
    if total == 0:
        print(
            f"\n0 rows written. EIA annual data lags — "
            f"try --years {config.MOST_RECENT_COMPLETE_YEAR}, "
            f"or run --discover to verify facet ids.",
            file=sys.stderr,
        )
    else:
        print(f"\nEIA: {total} production rows written to {config.DB_PATH}")
    return total


def main() -> None:
    p = argparse.ArgumentParser(description="Fetch EIA annual production.")
    p.add_argument("--years", nargs="+", type=int, default=config.DEFAULT_YEARS)
    p.add_argument("--commodity", nargs="+", default=list(config.EIA_INTL.keys()),
                   choices=list(config.EIA_INTL.keys()))
    p.add_argument("--discover", action="store_true",
                   help="Print live facet ids for each route and exit")
    args = p.parse_args()

    if args.discover:
        discover(config.require_key("EIA_KEY"))
        return
    run(args.years, args.commodity)


if __name__ == "__main__":
    main()
