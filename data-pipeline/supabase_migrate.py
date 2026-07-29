"""One-shot + re-runnable migration: create the Supabase (Postgres) schema and
load existing data into it. Idempotent — safe to re-run.

  python data-pipeline/supabase_migrate.py

Reads SUPABASE_DB_URL from .env. Source data: the local SQLite DB (raw tables)
and app/public/companies.json (curated companies).

Schema:
  price_history, news, export_flows, production, facility  — mirror the pipeline
  companies, company_footprint, company_assets             — relational companies
  map_snapshot(commodity, data jsonb)                       — precomputed per-
                                                             commodity map artifact
All tables get RLS + a public read policy so the browser can read them with the
anon key. Writes happen through this privileged connection (bypasses RLS).
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import Json, execute_values

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data-pipeline"))
import config  # noqa: E402  (loads .env)
import os

SQLITE = ROOT / "data" / "energy_map.db"
COMPANIES_JSON = ROOT / "app" / "public" / "companies.json"

DDL = """
create table if not exists price_history (
  commodity text not null, date date not null, price double precision,
  unit text, source text,
  unique (commodity, date, source));
create index if not exists ix_price_commodity_date on price_history (commodity, date);

create table if not exists news (
  id text primary key, title text, url text not null unique, source text,
  published_date date, snippet text, commodities_tags jsonb);
create index if not exists ix_news_date on news (published_date desc);

create table if not exists export_flows (
  reporter_iso text not null, partner_iso text not null, hs_code text not null,
  year integer not null, trade_value_usd double precision, quantity double precision,
  quantity_unit text, flow_source text not null default 'direct',
  unique (reporter_iso, partner_iso, hs_code, year, flow_source));
create index if not exists ix_flows_hs_year on export_flows (hs_code, year);
create index if not exists ix_flows_reporter on export_flows (reporter_iso);

create table if not exists production (
  country_iso text not null, commodity text not null, year integer not null,
  volume double precision, unit text, source text,
  unique (country_iso, commodity, year, source));
create index if not exists ix_prod_commodity_year on production (commodity, year);

create table if not exists facility (
  id text not null, name text, type text, country_iso text, lat double precision,
  lon double precision, commodity text, operator_company text,
  production_volume double precision, production_year integer, unit text,
  capacity double precision, status text, start_date text, photo_url text,
  photo_source text, source text,
  unique (source, id));
create index if not exists ix_facility_commodity on facility (commodity);

create table if not exists companies (
  id text primary key, name text, type text, hq text, founded integer,
  employees integer, revenue text, listing text, color text, blurb text,
  sort_order integer, logo text);
create table if not exists company_footprint (
  company_id text references companies(id) on delete cascade,
  commodity text, role text, presence integer, note text, sort_order integer);
create index if not exists ix_footprint_company on company_footprint (company_id);
create table if not exists company_assets (
  company_id text references companies(id) on delete cascade,
  name text, type text, commodity text, country text,
  lat double precision, lon double precision, note text, sort_order integer);
create index if not exists ix_assets_company on company_assets (company_id);

create table if not exists map_snapshot (
  commodity text primary key, data jsonb, updated_at timestamptz default now());

create table if not exists company_quotes (
  company_id text primary key references companies(id) on delete cascade,
  ticker text, exchange text, currency text,
  price_native double precision, price_usd double precision,
  prev_close_usd double precision, change_pct double precision,
  asof timestamptz default now());

create table if not exists company_price_history (
  company_id text references companies(id) on delete cascade,
  date date, price_usd double precision,
  primary key (company_id, date));
create index if not exists ix_cph_company on company_price_history (company_id);
"""

# Chart view for the Markets desk: one row per listed company with its live USD
# quote + day change and the full daily USD series as a [date, price] array.
FIRM_SERIES_VIEW = """
create or replace view public.firm_series with (security_invoker=on) as
  select h.company_id, c.name, c.logo, c.type,
         q.ticker, q.exchange, q.price_usd, q.change_pct,
         jsonb_agg(jsonb_build_array(h.date, h.price_usd) order by h.date) as points
  from company_price_history h
  join companies c on c.id = h.company_id
  left join company_quotes q on q.company_id = h.company_id
  group by h.company_id, c.name, c.logo, c.type, q.ticker, q.exchange,
           q.price_usd, q.change_pct;
grant select on public.firm_series to anon, authenticated;
"""

TABLES = ["price_history", "news", "export_flows", "production", "facility",
          "companies", "company_footprint", "company_assets", "map_snapshot",
          "company_quotes", "company_price_history"]


def apply_rls(cur):
    for t in TABLES:
        cur.execute(f"alter table public.{t} enable row level security;")
        cur.execute(f'drop policy if exists "public_read_{t}" on public.{t};')
        cur.execute(f'create policy "public_read_{t}" on public.{t} '
                    f"for select to anon, authenticated using (true);")
        cur.execute(f"grant select on public.{t} to anon, authenticated;")


def migrate_sqlite(cur):
    if not SQLITE.exists():
        print("  (no local SQLite — skipping raw-table migration)")
        return
    s = sqlite3.connect(SQLITE)
    s.row_factory = sqlite3.Row

    def copy(table, cols, conflict, transform=None):
        rows = s.execute(f"select {','.join(cols)} from {table}").fetchall()
        if not rows:
            print(f"  {table:16} 0 rows")
            return
        vals = [tuple((transform or (lambda r, c: r[c]))(r, c) for c in cols) for r in rows]
        execute_values(
            cur,
            f"insert into {table} ({','.join(cols)}) values %s "
            f"on conflict ({conflict}) do nothing",
            vals, page_size=1000)
        print(f"  {table:16} {len(vals):>7} rows")

    copy("price_history", ["commodity", "date", "price", "unit", "source"],
         "commodity, date, source")
    copy("production", ["country_iso", "commodity", "year", "volume", "unit", "source"],
         "country_iso, commodity, year, source")
    copy("export_flows", ["reporter_iso", "partner_iso", "hs_code", "year",
                          "trade_value_usd", "quantity", "quantity_unit", "flow_source"],
         "reporter_iso, partner_iso, hs_code, year, flow_source")
    copy("facility", ["id", "name", "type", "country_iso", "lat", "lon", "commodity",
                      "operator_company", "production_volume", "production_year", "unit",
                      "capacity", "status", "start_date", "photo_url", "photo_source", "source"],
         "source, id")
    copy("news", ["id", "title", "url", "source", "published_date", "snippet", "commodities_tags"],
         "url",
         transform=lambda r, c: (Json(json.loads(r[c])) if r[c] else None)
         if c == "commodities_tags" else r[c])
    s.close()


def load_companies(cur):
    if not COMPANIES_JSON.exists():
        print("  (no companies.json — skipping)")
        return
    data = json.loads(COMPANIES_JSON.read_text())["companies"]
    cur.execute("truncate company_footprint, company_assets;")
    for i, c in enumerate(data):
        cur.execute(
            "insert into companies (id,name,type,hq,founded,employees,revenue,listing,"
            "color,blurb,sort_order) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "on conflict (id) do update set name=excluded.name, type=excluded.type, "
            "hq=excluded.hq, founded=excluded.founded, employees=excluded.employees, "
            "revenue=excluded.revenue, listing=excluded.listing, color=excluded.color, "
            "blurb=excluded.blurb, sort_order=excluded.sort_order",
            (c["id"], c["name"], c["type"], c["hq"], c["founded"], c["employees"],
             c["revenue"], c["listing"], c["color"], c["blurb"], i))
        for j, f in enumerate(c["footprint"]):
            cur.execute("insert into company_footprint (company_id,commodity,role,"
                        "presence,note,sort_order) values (%s,%s,%s,%s,%s,%s)",
                        (c["id"], f["commodity"], f["role"], f["presence"], f.get("note", ""), j))
        for j, a in enumerate(c["assets"]):
            cur.execute("insert into company_assets (company_id,name,type,commodity,"
                        "country,lat,lon,note,sort_order) values (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (c["id"], a["name"], a["type"], a["commodity"], a["country"],
                         a["lat"], a["lon"], a.get("note", ""), j))
    print(f"  companies        {len(data):>7} (+ footprint + assets)")


def main():
    dsn = os.environ.get("SUPABASE_DB_URL", "").strip()
    if not dsn:
        sys.exit("Missing SUPABASE_DB_URL in .env")
    conn = psycopg2.connect(dsn, sslmode="require", connect_timeout=15)
    conn.autocommit = False
    cur = conn.cursor()
    print("→ creating schema…")
    cur.execute(DDL)
    print("→ enabling RLS + public read policies…")
    apply_rls(cur)
    print("→ migrating raw tables from SQLite…")
    migrate_sqlite(cur)
    print("→ loading companies…")
    load_companies(cur)
    print("→ creating firm_series view…")
    cur.execute(FIRM_SERIES_VIEW)
    conn.commit()
    # report
    print("\n=== Supabase now holds ===")
    for t in TABLES:
        cur.execute(f"select count(*) from {t}")
        print(f"  {t:16} {cur.fetchone()[0]:>7} rows")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
