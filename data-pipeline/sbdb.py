"""Supabase (Postgres) write layer — a drop-in for db.py used by the fetchers
when running against Supabase (env SUPABASE_POOLER_URL / SUPABASE_DB_URL set).
Same function names as db.py so callers just swap the import. The pipeline in
GitHub Actions uses the Transaction pooler (IPv4) via SUPABASE_POOLER_URL.
"""
from __future__ import annotations

import json
import os

import psycopg2
from psycopg2.extras import Json, execute_values


def _dsn() -> str:
    dsn = (os.environ.get("SUPABASE_POOLER_URL")
           or os.environ.get("SUPABASE_DB_URL") or "").strip()
    if not dsn:
        raise RuntimeError("No SUPABASE_POOLER_URL / SUPABASE_DB_URL in env")
    return dsn


def get_connection(*_a, **_k):
    return psycopg2.connect(_dsn(), sslmode="require", connect_timeout=20)


def init_db(_conn) -> None:
    """Schema is created once by supabase_migrate.py — nothing to do here."""


def upsert_news(conn, rows: list[dict]) -> int:
    if not rows:
        return 0
    vals = [(
        r["id"], r["title"], r["url"], r.get("source"), r.get("published_date"),
        r.get("snippet"),
        Json(json.loads(r["commodities_tags"])) if r.get("commodities_tags") else None,
        r.get("image"),
    ) for r in rows]
    cur = conn.cursor()
    execute_values(
        cur,
        "insert into news (id,title,url,source,published_date,snippet,commodities_tags,image) "
        "values %s on conflict (url) do update set title=excluded.title, "
        "source=excluded.source, published_date=excluded.published_date, "
        "snippet=excluded.snippet, commodities_tags=excluded.commodities_tags, "
        "image=coalesce(excluded.image, news.image)",
        vals, page_size=500)
    conn.commit()
    return len(rows)


def prune_news(conn, days: int = 30) -> int:
    cur = conn.cursor()
    cur.execute("delete from news where published_date < (current_date - %s::int)", (days,))
    conn.commit()
    return cur.rowcount


def upsert_prices(conn, rows: list[dict]) -> int:
    if not rows:
        return 0
    vals = [(r["commodity"], r["date"], r.get("price"), r.get("unit"), r.get("source"))
            for r in rows]
    cur = conn.cursor()
    execute_values(
        cur,
        "insert into price_history (commodity,date,price,unit,source) values %s "
        "on conflict (commodity,date,source) do update set price=excluded.price, "
        "unit=excluded.unit",
        vals, page_size=1000)
    conn.commit()
    return len(rows)


# --- raw map/production tables (so Comtrade/EIA/USGS fetchers can target Supabase) ---
_FACILITY_COLS = ("id", "name", "type", "country_iso", "lat", "lon", "commodity",
                  "operator_company", "production_volume", "production_year",
                  "unit", "capacity", "status", "start_date", "photo_url",
                  "photo_source", "source")


def upsert_flows(conn, rows: list[dict]) -> int:
    if not rows:
        return 0
    vals = [(r["reporter_iso"], r["partner_iso"], r["hs_code"], r["year"],
             r.get("trade_value_usd"), r.get("quantity"), r.get("quantity_unit"),
             r.get("flow_source", "direct")) for r in rows]
    cur = conn.cursor()
    execute_values(
        cur,
        "insert into export_flows (reporter_iso,partner_iso,hs_code,year,"
        "trade_value_usd,quantity,quantity_unit,flow_source) values %s "
        "on conflict (reporter_iso,partner_iso,hs_code,year,flow_source) do update set "
        "trade_value_usd=excluded.trade_value_usd, quantity=excluded.quantity, "
        "quantity_unit=excluded.quantity_unit",
        vals, page_size=1000)
    conn.commit()
    return len(rows)


def upsert_production(conn, rows: list[dict]) -> int:
    if not rows:
        return 0
    vals = [(r["country_iso"], r["commodity"], r["year"], r.get("volume"),
             r.get("unit"), r.get("source")) for r in rows]
    cur = conn.cursor()
    execute_values(
        cur,
        "insert into production (country_iso,commodity,year,volume,unit,source) values %s "
        "on conflict (country_iso,commodity,year,source) do update set "
        "volume=excluded.volume, unit=excluded.unit",
        vals, page_size=1000)
    conn.commit()
    return len(rows)


def upsert_facilities(conn, rows: list[dict]) -> int:
    if not rows:
        return 0
    vals = [tuple(r.get(c) for c in _FACILITY_COLS) for r in rows]
    updates = ", ".join(f"{c}=excluded.{c}" for c in _FACILITY_COLS
                        if c not in ("source", "id"))
    cur = conn.cursor()
    execute_values(
        cur,
        f"insert into facility ({','.join(_FACILITY_COLS)}) values %s "
        f"on conflict (source, id) do update set {updates}",
        vals, page_size=1000)
    conn.commit()
    return len(rows)
