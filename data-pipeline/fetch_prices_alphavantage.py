"""Complement FRED with Alpha Vantage prices (needs a free key in .env:
ALPHAVANTAGE_KEY). Alpha Vantage exposes a handful of commodities — WTI, Brent,
natural gas, copper, aluminium — potentially at higher frequency than FRED.

The free tier is heavily rate-limited (historically 5 req/min, 25 req/day — the
script sleeps 15s between calls; check your key's real limit before scaling a
scheduled run). Metals not on Alpha Vantage stay on FRED (or unavailable).

    python fetch_prices_alphavantage.py
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

import config
import store as db

API = "https://www.alphavantage.co/query"
RATE_SLEEP = 15  # seconds between calls (free tier ~5/min)

# commodity -> (Alpha Vantage function, interval, unit)
AV_SERIES = {
    "crude":     ("WTI", "daily", "USD/barrel (WTI)"),
    "lng":       ("NATURAL_GAS", "daily", "USD/MMBtu (Henry Hub)"),
    "copper":    ("COPPER", "monthly", "USD/tonne"),
    "aluminium": ("ALUMINUM", "monthly", "USD/tonne"),
}


def _fetch(func: str, interval: str, key: str) -> list[tuple[str, float]]:
    q = {"function": func, "interval": interval, "apikey": key}
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(q),
                                 headers={"User-Agent": "energy-map/1.0"})
    d = json.load(urllib.request.urlopen(req, timeout=60))
    if "data" not in d:
        note = d.get("Note") or d.get("Information") or d.get("Error Message") or str(d)[:120]
        raise RuntimeError(note)
    out = []
    for row in d["data"]:
        try:
            out.append((row["date"], float(row["value"])))
        except (KeyError, ValueError):
            continue
    return out


def run() -> dict:
    key = config.require_key("ALPHAVANTAGE_KEY")
    conn = db.get_connection()
    db.init_db(conn)
    report = {}
    for i, (commodity, (func, interval, unit)) in enumerate(AV_SERIES.items()):
        try:
            obs = _fetch(func, interval, key)
        except Exception as e:  # noqa: BLE001
            print(f"  {commodity:10} {func}: {e}")
            report[commodity] = {"points": 0, "error": str(e)}
            if i < len(AV_SERIES) - 1:
                time.sleep(RATE_SLEEP)
            continue
        rows = [{"commodity": commodity, "date": d, "price": p,
                 "unit": unit, "source": "AlphaVantage"} for d, p in obs]
        db.upsert_prices(conn, rows)
        report[commodity] = {"points": len(obs)}
        print(f"  {commodity:10} {func:12}: {len(obs)} points")
        if i < len(AV_SERIES) - 1:
            time.sleep(RATE_SLEEP)
    conn.close()
    return report


def main() -> None:
    print("Fetching Alpha Vantage prices (rate-limited):")
    run()


if __name__ == "__main__":
    main()
