"""Fetch live share prices for the listed companies into `company_quotes`.

Source: Yahoo Finance's public chart endpoint (keyless, one request per symbol,
covers every exchange). Prices are normalised to USD — 12 names quote on the
NYSE already; Aramco (SAR), Glencore (GBp) and PetroChina (HKD) are converted
with a same-day FX rate pulled from the same endpoint. State-owned / private
houses (Vitol, Trafigura, Gunvor, Mercuria, QatarEnergy, ADNOC, Pemex,
Sonatrach) are not listed, and the sanctioned MOEX names (Gazprom, Rosneft) are
deliberately skipped.

    python fetch_stocks.py
"""
from __future__ import annotations

import json
import time
import urllib.request

import store as db

CHART = ("https://query1.finance.yahoo.com/v8/finance/chart/"
         "{sym}?interval=1d&range=5d")
UA = {"User-Agent": "Mozilla/5.0 (compatible; energy-map/1.0)"}

# company_id -> (Yahoo symbol, exchange label, quote currency)
# USD via NYSE listing/ADR wherever one exists, native currency otherwise.
TICKERS = {
    "exxonmobil":    ("XOM", "NYSE", "USD"),
    "chevron":       ("CVX", "NYSE", "USD"),
    "conocophillips": ("COP", "NYSE", "USD"),
    "shell":         ("SHEL", "NYSE", "USD"),
    "bp":            ("BP", "NYSE", "USD"),
    "totalenergies": ("TTE", "NYSE", "USD"),
    "eni":           ("E", "NYSE", "USD"),
    "petrobras":     ("PBR", "NYSE", "USD"),
    "equinor":       ("EQNR", "NYSE", "USD"),
    "bhp":           ("BHP", "NYSE", "USD"),
    "riotinto":      ("RIO", "NYSE", "USD"),
    "vale":          ("VALE", "NYSE", "USD"),
    "aramco":        ("2222.SR", "Tadawul", "SAR"),
    "glencore":      ("GLEN.L", "LSE", "GBp"),   # pence
    "petrochina":    ("0857.HK", "HKEX", "HKD"),
}

# FX pair -> "USD per 1 unit". GBp (pence) handled specially (÷100 → GBP).
FX_PAIRS = {"SAR": "SARUSD=X", "GBp": "GBPUSD=X", "HKD": "HKDUSD=X"}


def _meta(sym: str) -> dict:
    for attempt in range(3):
        try:
            req = urllib.request.Request(CHART.format(sym=sym), headers=UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                d = json.load(r)
            return d["chart"]["result"][0]["meta"]
        except Exception:       # noqa: BLE001 — transient network / rate limit
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"no data for {sym}")


def _fx_rates() -> dict:
    rates = {"USD": 1.0}
    for cur, pair in FX_PAIRS.items():
        try:
            rates[cur] = float(_meta(pair)["regularMarketPrice"])
            time.sleep(0.5)
        except Exception as e:  # noqa: BLE001
            print(f"  FX {cur} ({pair}) FAILED: {e}")
    return rates


def _to_usd(price: float, currency: str, rates: dict) -> float | None:
    if currency == "USD":
        return price
    if currency == "GBp":                       # pence → GBP → USD
        r = rates.get("GBp")
        return price / 100 * r if r else None
    r = rates.get(currency)
    return price * r if r else None


def run() -> dict:
    rates = _fx_rates()
    conn = db.get_connection()
    db.init_db(conn)
    rows, report = [], {}
    for cid, (sym, exch, cur) in TICKERS.items():
        try:
            m = _meta(sym)
            px = float(m["regularMarketPrice"])
            prev = float(m.get("chartPreviousClose") or m.get("previousClose"))
        except Exception as e:  # noqa: BLE001
            print(f"  {cid:14} {sym:9} FAILED: {e}")
            report[cid] = {"error": str(e)}
            time.sleep(0.4)
            continue
        px_usd = _to_usd(px, cur, rates)
        prev_usd = _to_usd(prev, cur, rates)
        chg = (100 * (px - prev) / prev) if prev else None
        rows.append({"company_id": cid, "ticker": sym, "exchange": exch,
                     "currency": cur, "price_native": px, "price_usd": px_usd,
                     "prev_close_usd": prev_usd, "change_pct": chg})
        report[cid] = {"ticker": sym, "price_usd": px_usd, "change_pct": chg}
        arrow = "+" if (chg or 0) >= 0 else ""
        print(f"  {cid:14} {sym:9} ${px_usd:,.2f}  {arrow}{chg:.2f}%"
              if px_usd is not None else f"  {cid:14} {sym:9} (no USD)")
        time.sleep(0.4)
    n = db.upsert_quotes(conn, rows)
    conn.close()
    print(f"  → {n} quotes upserted")
    return report


def main() -> None:
    print("Fetching share prices (Yahoo Finance, keyless) → USD:")
    run()


if __name__ == "__main__":
    main()
