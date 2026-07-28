"""SQLite schema and connection helpers.

Two tables mirror the project brief. UNIQUE constraints make ingestion
idempotent: re-running a fetch upserts instead of duplicating rows.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import config

SCHEMA = """
-- reporter_iso is always the EXPORTER (source), partner_iso the IMPORTER
-- (destination). flow_source = 'direct' (exporter reported it, flow=X) or
-- 'mirror' (reconstructed from the importer's report, flow=M).
CREATE TABLE IF NOT EXISTS export_flows (
    reporter_iso    TEXT NOT NULL,
    partner_iso     TEXT NOT NULL,
    hs_code         TEXT NOT NULL,
    year            INTEGER NOT NULL,
    trade_value_usd REAL,
    quantity        REAL,
    quantity_unit   TEXT,
    flow_source     TEXT NOT NULL DEFAULT 'direct',
    UNIQUE (reporter_iso, partner_iso, hs_code, year, flow_source)
);

CREATE INDEX IF NOT EXISTS idx_flows_reporter ON export_flows (reporter_iso, year);
CREATE INDEX IF NOT EXISTS idx_flows_partner  ON export_flows (partner_iso, year);
CREATE INDEX IF NOT EXISTS idx_flows_hs       ON export_flows (hs_code, year);

CREATE TABLE IF NOT EXISTS production (
    country_iso TEXT NOT NULL,
    commodity   TEXT NOT NULL,
    year        INTEGER NOT NULL,
    volume      REAL,
    unit        TEXT,
    source      TEXT,
    UNIQUE (country_iso, commodity, year, source)
);

CREATE INDEX IF NOT EXISTS idx_prod_country ON production (country_iso, year);

-- Resolved flows: one row per (exporter, importer, hs). Per pair we keep the
-- most recent year available (2025 over 2024), and within that the direct
-- report over the mirror-derived one. Loading 2026 later auto-promotes it.
CREATE VIEW IF NOT EXISTS export_flows_latest AS
SELECT reporter_iso, partner_iso, hs_code, year,
       trade_value_usd, quantity, quantity_unit, flow_source
FROM (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY reporter_iso, partner_iso, hs_code
               ORDER BY year DESC, (flow_source = 'direct') DESC
           ) AS rn
    FROM export_flows
)
WHERE rn = 1;

CREATE VIEW IF NOT EXISTS production_latest AS
SELECT p.*
FROM production p
JOIN (
    SELECT country_iso, commodity, source, MAX(year) AS y
    FROM production
    GROUP BY country_iso, commodity, source
) m
  ON p.country_iso = m.country_iso
 AND p.commodity   = m.commodity
 AND p.source      = m.source
 AND p.year        = m.y;

-- Physical production sites (wells, LNG terminals, mines, refineries…).
-- Powers the "Infrastructure" view. operator/photo/dates left blank until the
-- Wikidata enrichment pass. UNIQUE(source,id) keeps ingestion idempotent.
CREATE TABLE IF NOT EXISTS facility (
    id                TEXT NOT NULL,
    name              TEXT,
    type              TEXT,          -- mine | refinery | well | lng_terminal | smelter
    country_iso       TEXT,
    lat               REAL,
    lon               REAL,
    commodity         TEXT,          -- frontend commodity key (crude, lng, copper…)
    operator_company  TEXT,
    production_volume REAL,
    production_year   INTEGER,
    unit              TEXT,
    capacity          REAL,
    status            TEXT,          -- operating | development | closed
    start_date        TEXT,
    photo_url         TEXT,
    photo_source      TEXT,
    source            TEXT,          -- GEM | USGS_MRDS | Wikidata | manual
    UNIQUE (source, id)
);
CREATE INDEX IF NOT EXISTS idx_facility_commodity ON facility (commodity);

-- News headlines (GDELT). Copyright-safe: title/url/source/date only, no full
-- text. commodities_tags is a JSON array, e.g. ["copper","nickel"].
CREATE TABLE IF NOT EXISTS news (
    id               TEXT NOT NULL,       -- url hash
    title            TEXT,
    url              TEXT NOT NULL,
    source           TEXT,
    published_date   TEXT,
    snippet          TEXT,
    commodities_tags TEXT,
    UNIQUE (url)
);
CREATE INDEX IF NOT EXISTS idx_news_date ON news (published_date);

-- Commodity price history (FRED / Alpha Vantage).
CREATE TABLE IF NOT EXISTS price_history (
    commodity TEXT NOT NULL,
    date      TEXT NOT NULL,
    price     REAL,
    unit      TEXT,
    source    TEXT,
    UNIQUE (commodity, date, source)
);
CREATE INDEX IF NOT EXISTS idx_price_commodity ON price_history (commodity, date);
"""


def get_connection(db_path: Path | str = config.DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def upsert_flows(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """Insert/replace export-flow rows. Returns count written."""
    if not rows:
        return 0
    conn.executemany(
        """
        INSERT INTO export_flows
            (reporter_iso, partner_iso, hs_code, year,
             trade_value_usd, quantity, quantity_unit, flow_source)
        VALUES
            (:reporter_iso, :partner_iso, :hs_code, :year,
             :trade_value_usd, :quantity, :quantity_unit, :flow_source)
        ON CONFLICT (reporter_iso, partner_iso, hs_code, year, flow_source) DO UPDATE SET
            trade_value_usd = excluded.trade_value_usd,
            quantity        = excluded.quantity,
            quantity_unit   = excluded.quantity_unit
        """,
        rows,
    )
    conn.commit()
    return len(rows)


FACILITY_COLS = ("id", "name", "type", "country_iso", "lat", "lon", "commodity",
                 "operator_company", "production_volume", "production_year",
                 "unit", "capacity", "status", "start_date", "photo_url",
                 "photo_source", "source")


def upsert_facilities(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """Insert/replace facility rows (keyed by source+id). Returns count."""
    if not rows:
        return 0
    cols = ", ".join(FACILITY_COLS)
    ph = ", ".join(f":{c}" for c in FACILITY_COLS)
    upd = ", ".join(f"{c}=excluded.{c}" for c in FACILITY_COLS
                    if c not in ("source", "id"))
    conn.executemany(
        f"INSERT INTO facility ({cols}) VALUES ({ph}) "
        f"ON CONFLICT (source, id) DO UPDATE SET {upd}",
        [{c: r.get(c) for c in FACILITY_COLS} for r in rows],
    )
    conn.commit()
    return len(rows)


def upsert_news(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """Insert/replace news rows (keyed by url). Returns count written."""
    if not rows:
        return 0
    conn.executemany(
        """
        INSERT INTO news (id, title, url, source, published_date, snippet, commodities_tags)
        VALUES (:id, :title, :url, :source, :published_date, :snippet, :commodities_tags)
        ON CONFLICT (url) DO UPDATE SET
            title = excluded.title, source = excluded.source,
            published_date = excluded.published_date, snippet = excluded.snippet,
            commodities_tags = excluded.commodities_tags
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def upsert_prices(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """Insert/replace price_history rows. Returns count written."""
    if not rows:
        return 0
    conn.executemany(
        """
        INSERT INTO price_history (commodity, date, price, unit, source)
        VALUES (:commodity, :date, :price, :unit, :source)
        ON CONFLICT (commodity, date, source) DO UPDATE SET
            price = excluded.price, unit = excluded.unit
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def upsert_production(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """Insert/replace production rows. Returns count written."""
    if not rows:
        return 0
    conn.executemany(
        """
        INSERT INTO production
            (country_iso, commodity, year, volume, unit, source)
        VALUES
            (:country_iso, :commodity, :year, :volume, :unit, :source)
        ON CONFLICT (country_iso, commodity, year, source) DO UPDATE SET
            volume = excluded.volume,
            unit   = excluded.unit
        """,
        rows,
    )
    conn.commit()
    return len(rows)
