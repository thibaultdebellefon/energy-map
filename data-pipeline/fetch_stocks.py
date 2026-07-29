"""Fetch share prices for the listed companies → `company_quotes` (latest USD
snapshot) and `company_price_history` (daily USD series for the chart).

Source: Yahoo Finance's public chart endpoint (keyless, one request per symbol,
covers every exchange). Prices are normalised to USD — 12 names quote on the
NYSE already; Aramco (SAR), Glencore (GBp) and PetroChina (HKD) are converted
with a per-day FX rate pulled from the same endpoint (forward-filled onto each
trading day). State-owned / private houses (Vitol, Trafigura, Gunvor, Mercuria,
QatarEnergy, ADNOC, Pemex, Sonatrach) are not listed, and the sanctioned MOEX
names (Gazprom, Rosneft) are deliberately skipped.

    python fetch_stocks.py
"""
from __future__ import annotations

import bisect
import json
import time
import urllib.request

import store as db

CHART = ("https://query1.finance.yahoo.com/v8/finance/chart/"
         "{sym}?interval=1d&range={rng}")
UA = {"User-Agent": "Mozilla/5.0 (compatible; energy-map/1.0)"}
HIST_RANGE = "2y"

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


def _chart(sym: str, rng: str = "5d") -> dict:
    for attempt in range(3):
        try:
            req = urllib.request.Request(CHART.format(sym=sym, rng=rng), headers=UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                d = json.load(r)
            return d["chart"]["result"][0]
        except Exception:       # noqa: BLE001 — transient network / rate limit
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"no data for {sym}")


def _daily(result: dict) -> list[tuple[str, float]]:
    """(date, close) per trading day, skipping missing bars."""
    ts = result.get("timestamp") or []
    closes = (result.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
    out = []
    for t, c in zip(ts, closes):
        if c is None:
            continue
        out.append((time.strftime("%Y-%m-%d", time.gmtime(t)), float(c)))
    return out


class _FX:
    """Per-day USD conversion, forward-filled onto any trading day."""

    def __init__(self):
        self.series = {}   # currency -> (sorted dates[], rates[])
        for cur, pair in FX_PAIRS.items():
            try:
                hist = _daily(_chart(pair, HIST_RANGE))
                self.series[cur] = ([d for d, _ in hist], [r for _, r in hist])
                time.sleep(0.4)
            except Exception as e:  # noqa: BLE001
                print(f"  FX {cur} ({pair}) FAILED: {e}")

    def rate(self, currency: str, date: str) -> float | None:
        key = "GBp" if currency == "GBp" else currency
        s = self.series.get(key)
        if not s or not s[0]:
            return None
        i = bisect.bisect_right(s[0], date) - 1
        return s[1][i] if i >= 0 else s[1][0]

    def to_usd(self, price: float, currency: str, date: str) -> float | None:
        if currency == "USD":
            return price
        r = self.rate(currency, date)
        if r is None:
            return None
        return price / 100 * r if currency == "GBp" else price * r


def run() -> dict:
    fx = _FX()
    conn = db.get_connection()
    db.init_db(conn)
    quotes, hist_rows, report = [], [], {}
    today = time.strftime("%Y-%m-%d", time.gmtime())
    for cid, (sym, exch, cur) in TICKERS.items():
        try:
            # short range → reliable live price + true previous close (day change)
            m = _chart(sym, "5d")["meta"]
            px = float(m["regularMarketPrice"])
            prev = float(m.get("chartPreviousClose") or m.get("previousClose"))
            hist = _chart(sym, HIST_RANGE)          # long range → chart series
        except Exception as e:  # noqa: BLE001
            print(f"  {cid:14} {sym:9} FAILED: {e}")
            report[cid] = {"error": str(e)}
            time.sleep(0.4)
            continue
        px_usd = fx.to_usd(px, cur, today)
        prev_usd = fx.to_usd(prev, cur, today)
        chg = (100 * (px - prev) / prev) if prev else None   # native → same %
        quotes.append({"company_id": cid, "ticker": sym, "exchange": exch,
                       "currency": cur, "price_native": px, "price_usd": px_usd,
                       "prev_close_usd": prev_usd, "change_pct": chg})
        n = 0
        for d, close in _daily(hist):
            usd = fx.to_usd(close, cur, d)
            if usd is not None:
                hist_rows.append({"company_id": cid, "date": d, "price_usd": usd})
                n += 1
        report[cid] = {"ticker": sym, "price_usd": px_usd, "change_pct": chg, "points": n}
        arrow = "+" if (chg or 0) >= 0 else ""
        print(f"  {cid:14} {sym:9} ${px_usd:,.2f}  {arrow}{chg:.2f}%  ({n} pts)"
              if px_usd is not None else f"  {cid:14} {sym:9} (no USD)")
        time.sleep(0.4)
    db.upsert_quotes(conn, quotes)
    db.upsert_price_history(conn, hist_rows)
    conn.close()
    print(f"  → {len(quotes)} quotes, {len(hist_rows)} history points upserted")
    return report


def main() -> None:
    print("Fetching share prices (Yahoo Finance, keyless) → USD:")
    run()


if __name__ == "__main__":
    main()
