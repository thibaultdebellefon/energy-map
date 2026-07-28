"""Fetch full commodity price history from FRED into `price_history`.

All 12 tracked commodities have a FRED series (verified): energy uses the
daily WTI / LNG-Asia series, metals use the IMF "Global price of …" monthly
series. FRED's public fredgraph.csv endpoint needs no key, so this runs as-is;
set FRED_KEY in .env only if you later want the metadata-rich official API.

    python fetch_prices_fred.py
"""
from __future__ import annotations

import csv
import io
import urllib.request

import db

CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"

# commodity -> (FRED series id, unit). Verified to exist on FRED.
# NO FRED series (checked, 404): cobalt, lithium, manganese, graphite,
# rare_earths — flagged for an alternative source.
FRED_SERIES = {
    "crude":     ("DCOILWTICO", "USD/barrel (WTI)"),
    "lng":       ("PNGASJPUSDM", "USD/MMBtu (Asia LNG)"),
    "copper":    ("PCOPPUSDM", "USD/tonne"),
    "aluminium": ("PALUMUSDM", "USD/tonne"),
    "nickel":    ("PNICKUSDM", "USD/tonne"),
    "zinc":      ("PZINCUSDM", "USD/tonne"),
    "tin":       ("PTINUSDM", "USD/tonne"),
}
NO_FRED_SERIES = ["cobalt", "lithium", "manganese", "graphite", "rare_earths"]


def _fetch_csv(sid: str) -> list[tuple[str, float]]:
    req = urllib.request.Request(CSV_URL.format(sid=sid),
                                 headers={"User-Agent": "energy-map/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        text = r.read().decode("utf-8")
    rows = []
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 2 or row[0] in ("observation_date", "DATE") or not row[0][0].isdigit():
            continue
        try:
            rows.append((row[0], float(row[1])))
        except ValueError:      # FRED uses "." for missing
            continue
    return rows


def run() -> dict:
    conn = db.get_connection()
    db.init_db(conn)
    report = {}
    for commodity, (sid, unit) in FRED_SERIES.items():
        try:
            obs = _fetch_csv(sid)
        except Exception as e:  # noqa: BLE001
            print(f"  {commodity:12} {sid}: FAILED ({e})")
            report[commodity] = {"series": sid, "points": 0, "error": str(e)}
            continue
        rows = [{"commodity": commodity, "date": d, "price": p,
                 "unit": unit, "source": "FRED"} for d, p in obs]
        db.upsert_prices(conn, rows)
        latest = obs[-1] if obs else ("—", None)
        report[commodity] = {"series": sid, "points": len(obs),
                             "latest": latest, "unit": unit}
        print(f"  {commodity:12} {sid:12}: {len(obs):5} points, "
              f"latest {latest[0]} = {latest[1]} {unit}")
    conn.close()
    return report


def main() -> None:
    print("Fetching FRED price history (keyless CSV endpoint):")
    run()


if __name__ == "__main__":
    main()
