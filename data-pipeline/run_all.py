"""Orchestrate the full pipeline and print a data-quality summary (task 5).

    python run_all.py --years 2023          # fetch + normalize + summary (needs keys)
    python run_all.py --selftest            # synthetic data, no API keys needed

--selftest inserts a few hand-made rows to prove the schema, normalisation and
summary logic end-to-end WITHOUT calling any API. It is clearly labelled and
never presented as real data.
"""
from __future__ import annotations

import argparse

import config
import db
import fetch_comtrade
import fetch_eia
import normalize_countries as norm


def summarize(conn) -> None:
    print("\n" + "=" * 60)
    print("DATA SUMMARY")
    print("=" * 60)

    # --- Raw ingestion per year (transparency) ----------------------------
    print("Raw rows ingested per year:")
    for row in conn.execute(
        "SELECT year, COUNT(*) n FROM export_flows GROUP BY year ORDER BY year"
    ):
        print(f"    flows {row['year']}: {row['n']}")
    for row in conn.execute(
        "SELECT year, COUNT(*) n FROM production GROUP BY year ORDER BY year"
    ):
        print(f"    production {row['year']}: {row['n']}")

    # --- Coalesced "latest available" view (2025-priority, 2024-fallback) --
    flows = conn.execute("SELECT COUNT(*) FROM export_flows_latest").fetchone()[0]
    prod = conn.execute("SELECT COUNT(*) FROM production_latest").fetchone()[0]
    print(f"\nCoalesced (latest-available):")
    print(f"    export_flows_latest rows : {flows}")
    print(f"    production_latest rows   : {prod}")

    print("    flow provenance by year:")
    for row in conn.execute(
        "SELECT year, COUNT(*) n FROM export_flows_latest GROUP BY year ORDER BY year DESC"
    ):
        print(f"        {row['year']}: {row['n']} flows")
    print("    flow provenance by source:")
    for row in conn.execute(
        "SELECT flow_source, COUNT(*) n FROM export_flows_latest "
        "GROUP BY flow_source ORDER BY n DESC"
    ):
        print(f"        {row['flow_source']}: {row['n']} flows")
    print("    production provenance by year:")
    for row in conn.execute(
        "SELECT year, COUNT(*) n FROM production_latest GROUP BY year ORDER BY year DESC"
    ):
        print(f"        {row['year']}: {row['n']} rows")

    reporters = conn.execute(
        "SELECT COUNT(DISTINCT reporter_iso) FROM export_flows_latest").fetchone()[0]
    partners = conn.execute(
        "SELECT COUNT(DISTINCT partner_iso) FROM export_flows_latest").fetchone()[0]
    prod_countries = conn.execute(
        "SELECT COUNT(DISTINCT country_iso) FROM production_latest").fetchone()[0]
    print(f"    distinct exporters: {reporters} | partners: {partners} "
          f"| producing countries: {prod_countries}")

    print("\nBy commodity (coalesced):")
    for row in conn.execute(
        "SELECT hs_code, COUNT(*) n FROM export_flows_latest GROUP BY hs_code ORDER BY hs_code"
    ):
        label = config.COMMODITY_BY_HS.get(row["hs_code"], "?")
        print(f"    {row['hs_code']} ({label}): {row['n']} flows")

    print("\nAnomalies (coalesced):")
    null_value = conn.execute(
        "SELECT COUNT(*) FROM export_flows_latest WHERE trade_value_usd IS NULL").fetchone()[0]
    null_qty = conn.execute(
        "SELECT COUNT(*) FROM export_flows_latest WHERE quantity IS NULL").fetchone()[0]
    null_vol = conn.execute(
        "SELECT COUNT(*) FROM production_latest WHERE volume IS NULL").fetchone()[0]
    print(f"    flows missing trade_value_usd : {null_value}")
    print(f"    flows missing quantity        : {null_qty}")
    print(f"    production missing volume     : {null_vol}")

    # A real duplicate = same key AND same source. Pairs present as both direct
    # and mirror are expected overlap, not duplicates — report them separately.
    dup_flows = conn.execute(
        "SELECT COUNT(*) FROM (SELECT 1 FROM export_flows "
        "GROUP BY reporter_iso, partner_iso, hs_code, year, flow_source "
        "HAVING COUNT(*) > 1)"
    ).fetchone()[0]
    overlap = conn.execute(
        "SELECT COUNT(*) FROM (SELECT 1 FROM export_flows "
        "GROUP BY reporter_iso, partner_iso, hs_code, year HAVING COUNT(*) > 1)"
    ).fetchone()[0]
    print(f"    true duplicate flow keys      : {dup_flows}")
    print(f"    pairs w/ both direct+mirror   : {overlap} (expected overlap, not an anomaly)")

    print("\nTop 5 exporters by total trade value (coalesced):")
    for row in conn.execute(
        "SELECT reporter_iso, SUM(trade_value_usd) v FROM export_flows_latest "
        "GROUP BY reporter_iso ORDER BY v DESC LIMIT 5"
    ):
        v = row["v"] or 0
        print(f"    {row['reporter_iso']}: ${v:,.0f}")


def run_selftest() -> None:
    print(">>> SELF-TEST — SYNTHETIC DATA (not from any API) <<<")
    conn = db.get_connection(":memory:")
    db.init_db(conn)

    # Synthetic flows. Includes: a World aggregate (must be dropped), and one
    # pair (SAU->CHN) present as BOTH direct and mirror to prove direct wins.
    db.upsert_flows(conn, [
        {"reporter_iso": "SAU", "partner_iso": "CHN", "hs_code": "2709",
         "year": 2023, "trade_value_usd": 5e10, "quantity": 1e8, "quantity_unit": "kg",
         "flow_source": "direct"},
        {"reporter_iso": "SAU", "partner_iso": "CHN", "hs_code": "2709",
         "year": 2023, "trade_value_usd": 5.4e10, "quantity": 1e8, "quantity_unit": "kg",
         "flow_source": "mirror"},   # CIF > FOB; should lose to direct
        {"reporter_iso": "RUS", "partner_iso": "IND", "hs_code": "2709",
         "year": 2023, "trade_value_usd": 3e10, "quantity": 8e7, "quantity_unit": "kg",
         "flow_source": "mirror"},   # RUS only via mirror
        {"reporter_iso": "QAT", "partner_iso": "JPN", "hs_code": "271111",
         "year": 2023, "trade_value_usd": 2e10, "quantity": None, "quantity_unit": "kg",
         "flow_source": "direct"},
        {"reporter_iso": "USA", "partner_iso": "W00", "hs_code": "2709",
         "year": 2023, "trade_value_usd": 9e10, "quantity": 2e8, "quantity_unit": "kg",
         "flow_source": "direct"},
    ])
    # Synthetic production: EIA-style codes + one region aggregate (OPEC).
    db.upsert_production(conn, [
        {"country_iso": "SAU", "commodity": "crude_oil", "year": 2023,
         "volume": 12000.0, "unit": "TBPD", "source": "EIA"},
        {"country_iso": "USA", "commodity": "crude_oil", "year": 2023,
         "volume": 12900.0, "unit": "TBPD", "source": "EIA"},
        {"country_iso": "KSV", "commodity": "natural_gas", "year": 2023,
         "volume": 0.0, "unit": "BCF", "source": "EIA"},   # EIA KSV -> XKX
        {"country_iso": "OPEC", "commodity": "crude_oil", "year": 2023,
         "volume": 30000.0, "unit": "TBPD", "source": "EIA"},
    ])

    report = norm.normalize_db(conn)
    norm.print_report(report)
    summarize(conn)

    # Assertions — prove the pipeline behaved correctly.
    assert conn.execute(
        "SELECT COUNT(*) FROM export_flows WHERE partner_iso='W00'").fetchone()[0] == 0, \
        "World aggregate should be dropped"
    assert conn.execute(
        "SELECT COUNT(*) FROM production WHERE country_iso='OPEC'").fetchone()[0] == 0, \
        "OPEC aggregate should be dropped"
    assert conn.execute(
        "SELECT COUNT(*) FROM production WHERE country_iso='XKX'").fetchone()[0] == 1, \
        "KSV should be remapped to XKX"
    # SAU->CHN exists as both direct and mirror; resolved view must keep direct.
    row = conn.execute(
        "SELECT flow_source, trade_value_usd FROM export_flows_latest "
        "WHERE reporter_iso='SAU' AND partner_iso='CHN'").fetchone()
    assert row["flow_source"] == "direct" and row["trade_value_usd"] == 5e10, \
        "direct should win over mirror for SAU->CHN"
    # RUS is only present via mirror — must still appear in the resolved view.
    assert conn.execute(
        "SELECT flow_source FROM export_flows_latest "
        "WHERE reporter_iso='RUS'").fetchone()["flow_source"] == "mirror", \
        "RUS should be captured via mirror"
    conn.close()
    print("\n>>> SELF-TEST PASSED <<<")


def run_pipeline(years, hs_codes, commodities) -> None:
    print(f"Running pipeline for years={years}")
    fetch_comtrade.run(hs_codes, years, ["X", "M"])  # direct + mirror
    fetch_eia.run(years, commodities)

    conn = db.get_connection()
    db.init_db(conn)
    report = norm.normalize_db(conn)
    norm.print_report(report)
    summarize(conn)
    conn.close()


def main() -> None:
    p = argparse.ArgumentParser(description="Run the full ingestion pipeline.")
    p.add_argument("--years", nargs="+", type=int, default=config.DEFAULT_YEARS)
    p.add_argument("--hs", nargs="+", default=list(config.HS_CODES.values()))
    p.add_argument("--commodity", nargs="+", default=list(config.EIA_INTL.keys()))
    p.add_argument("--selftest", action="store_true",
                   help="Validate schema+normalisation+summary on synthetic data")
    args = p.parse_args()

    if args.selftest:
        run_selftest()
        return
    run_pipeline(args.years, args.hs, args.commodity)


if __name__ == "__main__":
    main()
