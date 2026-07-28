"""Harmonise country codes across Comtrade and EIA to canonical ISO3.

Run after the fetchers. It:
  1. Rewrites *_iso / country_iso columns to canonical ISO3 (via country_maps).
  2. Deletes aggregate rows (World, OPEC, EU…) — reporting what was dropped.
  3. Prints a reconciliation report: unknown codes and coverage gaps between
     the trade side (export_flows) and the production side (production).

Usage:
    python normalize_countries.py
"""
from __future__ import annotations

import sqlite3

import config
import db
from country_maps import is_aggregate, to_iso3


def _distinct(conn, table, col) -> set[str]:
    return {row[0] for row in conn.execute(
        f"SELECT DISTINCT {col} FROM {table} WHERE {col} IS NOT NULL")}


def normalize_db(conn: sqlite3.Connection) -> dict:
    report = {"remapped": [], "dropped_aggregates": {}, "unknown": {}}

    # --- export_flows: reporter + partner columns -------------------------
    for col, source in [("reporter_iso", "comtrade"), ("partner_iso", "comtrade")]:
        for code in _distinct(conn, "export_flows", col):
            canon = to_iso3(code, source)
            if canon is None:
                if is_aggregate(code):
                    n = conn.execute(
                        f"DELETE FROM export_flows WHERE {col} = ?", (code,)
                    ).rowcount
                    report["dropped_aggregates"][f"flows.{col}:{code}"] = n
                else:
                    report["unknown"].setdefault(f"flows.{col}", []).append(code)
            elif canon != code:
                conn.execute(
                    f"UPDATE export_flows SET {col} = ? WHERE {col} = ?", (canon, code))
                report["remapped"].append((f"flows.{col}", code, canon))

    # --- production: country_iso ------------------------------------------
    for code in _distinct(conn, "production", "country_iso"):
        canon = to_iso3(code, "eia")
        if canon is None:
            if is_aggregate(code):
                n = conn.execute(
                    "DELETE FROM production WHERE country_iso = ?", (code,)
                ).rowcount
                report["dropped_aggregates"][f"production:{code}"] = n
            else:
                report["unknown"].setdefault("production.country_iso", []).append(code)
        elif canon != code:
            conn.execute(
                "UPDATE production SET country_iso = ? WHERE country_iso = ?", (canon, code))
            report["remapped"].append(("production.country_iso", code, canon))

    conn.commit()

    # --- coverage reconciliation ------------------------------------------
    exporters = _distinct(conn, "export_flows", "reporter_iso")
    producers = _distinct(conn, "production", "country_iso")
    report["produces_but_no_exports"] = sorted(producers - exporters)
    report["exports_but_no_production"] = sorted(exporters - producers)
    return report


def print_report(report: dict) -> None:
    print("\n=== Country normalisation report ===")
    print(f"Remapped codes      : {len(report['remapped'])}")
    for scope, src, dst in report["remapped"]:
        print(f"    {scope}: {src} -> {dst}")

    dropped = report["dropped_aggregates"]
    print(f"Aggregate rows dropped: {sum(dropped.values())} across {len(dropped)} codes")
    for k, n in dropped.items():
        print(f"    {k}: {n} rows")

    unknown = report["unknown"]
    total_unknown = sum(len(v) for v in unknown.values())
    print(f"Unknown (non-ISO3) codes: {total_unknown}")
    for scope, codes in unknown.items():
        print(f"    {scope}: {sorted(set(codes))}")

    print(f"Producers with no export flows : {len(report['produces_but_no_exports'])}")
    print(f"    {report['produces_but_no_exports']}")
    print(f"Exporters with no production    : {len(report['exports_but_no_production'])}")
    print(f"    {report['exports_but_no_production']}")


def main() -> None:
    conn = db.get_connection()
    db.init_db(conn)
    report = normalize_db(conn)
    conn.close()
    print_report(report)


if __name__ == "__main__":
    main()
