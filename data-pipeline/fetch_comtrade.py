"""Fetch bilateral export flows from UN Comtrade API v1 into SQLite.

Usage:
    python fetch_comtrade.py --hs 2709 271111 --years 2023
    python fetch_comtrade.py                      # uses config defaults

For each (HS code, year) it pulls all reporter -> partner export flows in one
call (a single HS/year is well under the 100k-row ceiling), filters out World
and aggregate partners, and upserts into `export_flows`.
"""
from __future__ import annotations

import argparse
import sys
import time

import requests

import config
import db
from country_maps import is_aggregate


def _to_float(value) -> float | None:
    try:
        if value in (None, "", "..", "-"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_one(hs_code: str, year: int, key: str, flow: str) -> list[dict]:
    """One API call for a single HS code + year. Returns cleaned rows.

    flow='X' -> direct exports (reporter=exporter). flow='M' -> imports, which
    we mirror: the importer's report of buying from a partner becomes an
    exporter->importer flow, so we SWAP reporter/partner and tag flow_source.
    `key` may be "" — the API then serves the limited anonymous tier.
    """
    mirror = flow == "M"
    flow_source = "mirror" if mirror else "direct"
    url = f"{config.COMTRADE_BASE}/{config.COMTRADE_TYPE}/{config.COMTRADE_FREQ}/{config.COMTRADE_CL}"
    params = {
        "reporterCode": "",       # all reporters
        "partnerCode": "",        # all partners
        "partner2Code": "0",
        "period": str(year),
        "cmdCode": hs_code,
        "flowCode": flow,         # X = export
        # Keep only the aggregate total per pair: motCode 0 = all transport
        # modes, customsCode C00 = all customs procedures. Without this the API
        # returns one row per mode/customs breakdown, which would collapse
        # arbitrarily under our UNIQUE key and understate trade values.
        "motCode": "0",
        "customsCode": "C00",
        "includeDesc": "true",
    }
    headers = {"Ocp-Apim-Subscription-Key": key} if key else {}

    data = _request_with_retry(url, params, headers)
    count = data.get("count", 0)
    if count >= config.COMTRADE_ROW_CAP:
        print(
            f"  ! WARNING hs={hs_code} year={year}: hit {config.COMTRADE_ROW_CAP}-row "
            f"cap — results may be truncated. Consider splitting by reporter.",
            file=sys.stderr,
        )

    rows: list[dict] = []
    skipped_agg = 0
    for r in data.get("data", []):
        rep = (r.get("reporterISO") or "").upper().strip()
        par = (r.get("partnerISO") or "").upper().strip()
        # For mirror (imports), the reporter is the importer and the partner is
        # the exporter — swap so reporter_iso is always the exporter/source.
        exporter, importer = (par, rep) if mirror else (rep, par)
        if not exporter or not importer:
            continue
        if is_aggregate(exporter) or is_aggregate(importer):
            skipped_agg += 1
            continue
        rows.append(
            {
                "reporter_iso": exporter,
                "partner_iso": importer,
                "hs_code": str(r.get("cmdCode") or hs_code),
                "year": int(r.get("period") or year),
                "trade_value_usd": _to_float(r.get("primaryValue")),
                "quantity": _to_float(r.get("qty")),
                "quantity_unit": r.get("qtyUnitAbbr") or r.get("qtyUnitCode"),
                "flow_source": flow_source,
            }
        )

    print(
        f"  hs={hs_code} year={year} flow={flow} ({flow_source}): {count} rows "
        f"returned, {len(rows)} bilateral kept, {skipped_agg} aggregates dropped"
    )
    return rows


def _request_with_retry(url, params, headers, attempts: int = 4) -> dict:
    delay = 2.0
    for attempt in range(1, attempts + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=60)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise requests.HTTPError(f"HTTP {resp.status_code}")
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            if attempt == attempts:
                raise SystemExit(f"Comtrade request failed after {attempts} tries: {exc}")
            print(f"  retry {attempt}/{attempts} in {delay:.0f}s ({exc})", file=sys.stderr)
            time.sleep(delay)
            delay *= 2
    return {}


def run(hs_codes: list[str], years: list[int], flows: list[str]) -> int:
    key = config.optional_key("COMTRADE_KEY")
    if not key:
        print(
            "  ! No COMTRADE_KEY set — using the anonymous tier (small quotas, "
            "results may be truncated). Get a free token at "
            "https://comtradedeveloper.un.org/ for 500 calls/day, 100k rows/call.",
            file=sys.stderr,
        )
    conn = db.get_connection()
    db.init_db(conn)

    total = 0
    for hs_code in hs_codes:
        for year in years:
            for flow in flows:  # 'X' = direct exports, 'M' = mirror imports
                rows = fetch_one(hs_code, year, key, flow)
                total += db.upsert_flows(conn, rows)
                time.sleep(config.COMTRADE_RATE_LIMIT_S)  # >= 1 req/sec

    conn.close()
    if total == 0:
        print(
            f"\n0 rows written. Comtrade annual data lags ~1 year — "
            f"try --years {config.MOST_RECENT_COMPLETE_YEAR}.",
            file=sys.stderr,
        )
    else:
        print(f"\nComtrade: {total} flow rows written to {config.DB_PATH}")
    return total


def main() -> None:
    p = argparse.ArgumentParser(description="Fetch Comtrade bilateral export flows.")
    p.add_argument("--hs", nargs="+", default=list(config.HS_CODES.values()),
                   help="HS codes (default: crude oil 2709 + LNG 271111)")
    p.add_argument("--years", nargs="+", type=int, default=config.DEFAULT_YEARS,
                   help="Years (default: config.DEFAULT_YEARS)")
    p.add_argument("--flows", nargs="+", default=["X", "M"],
                   help="Flow codes to fetch: X=direct exports, M=mirror imports")
    args = p.parse_args()
    run(args.hs, args.years, args.flows)


if __name__ == "__main__":
    main()
