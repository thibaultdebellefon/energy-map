"""Build the frontend data bundle from the SQLite database.

Reads the resolved views (export_flows_latest, production_latest), aggregates
per country, and writes app/public/data.json. Also vendors the two static
assets the map needs (D3 + world geometry) so the app runs fully offline once
built.

    python app/build_data.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

# Reuse the pipeline's config/db and the canonical ISO3 set.
APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
sys.path.insert(0, str(REPO_ROOT / "data-pipeline"))

import config  # noqa: E402
import db  # noqa: E402
from country_maps import ISO3_ALPHA3  # noqa: E402
from routes_def import ROUTES  # noqa: E402

PUBLIC = APP_DIR / "public"
VENDOR = PUBLIC / "vendor"

# Commodity registry: one entry per tradeable HS series the frontend exposes.
# (key, HS code, label, group, hex color, production-table commodity, prod unit)
COMMODITIES = [
    ("crude",   "2709",   "Crude oil",            "Energy", "#F4A93C", "crude_oil",   "TBPD"),
    ("lng",     "271111", "LNG",                  "Energy", "#46D5E4", "natural_gas", "BCF"),
    # refined / traded metal
    ("copper",    "7403",   "Copper (refined)",   "Metal · refined", "#E07B4B", "copper",      "t"),
    ("aluminium", "7601",   "Aluminium",          "Metal · refined", "#9FB6C4", "aluminium",   "t"),
    ("cobalt",    "8105",   "Cobalt",             "Metal · refined", "#5B7BE8", "cobalt",      "t"),
    ("lithium",   "283691", "Lithium",            "Metal · refined", "#B7D94A", "lithium",     "t"),
    ("nickel",    "7502",   "Nickel",             "Metal · refined", "#7ED9A6", "nickel",      "t"),
    ("ree",       "280530", "Rare-earth metals",  "Metal · refined", "#E75FB5", "rare_earths", "t"),
    ("ree_cmp",   "2846",   "Rare-earth compounds","Metal · refined","#C257A0", "rare_earths", "t"),
    ("zinc",      "7901",   "Zinc",               "Metal · refined", "#AEB7C0", "zinc",        "t"),
    ("tin",       "8001",   "Tin",                "Metal · refined", "#C9C9DC", "tin",         "t"),
    ("manganese", "8111",   "Manganese",          "Metal · refined", "#CF7FA6", "manganese",   "t"),
    # raw ore / concentrate
    ("copper_ore",    "2603", "Copper ore",       "Metal · ore", "#B5651D", "copper",      "t"),
    ("bauxite",       "2606", "Bauxite (Al ore)", "Metal · ore", "#C08552", "aluminium",   "t"),
    ("cobalt_ore",    "2605", "Cobalt ore",       "Metal · ore", "#3E5DB8", "cobalt",      "t"),
    ("nickel_ore",    "2604", "Nickel ore",       "Metal · ore", "#5AA87E", "nickel",      "t"),
    ("zinc_ore",      "2608", "Zinc ore",         "Metal · ore", "#828B94", "zinc",        "t"),
    ("tin_ore",       "2609", "Tin ore",          "Metal · ore", "#9A9AB4", "tin",         "t"),
    ("manganese_ore", "2602", "Manganese ore",    "Metal · ore", "#AD5F82", "manganese",   "t"),
    ("graphite",      "2504", "Graphite (natural)","Metal · refined","#7B828C", "graphite",    "t"),
]
# Extra HS codes merged into an existing metal so its trade total is complete
# (a single HS captures only part of a metal's real trade).
EXTRA_HS = {
    "282520": "lithium",    # lithium oxide & hydroxide (+ carbonate 283691)
    "720260": "nickel",     # ferro-nickel  (+ unwrought 7502)
    "7501":   "nickel",     # nickel mattes / oxide sinters
    "720211": "manganese",  # ferro-manganese >2%C (+ metal 8111)
    "720219": "manganese",  # ferro-manganese ≤2%C
}
TRADE = {**{hs: key for key, hs, *_ in COMMODITIES}, **EXTRA_HS}  # HS -> frontend key
PROD_KEYS = {c[5] for c in COMMODITIES if c[5]}           # production commodities we keep
ENERGY_KEYS = {"crude", "lng"}

ASSETS = {
    VENDOR / "d3.min.js": "https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js",
    PUBLIC / "world.geojson":
        "https://cdn.jsdelivr.net/gh/nvkelso/natural-earth-vector@master/"
        "geojson/ne_110m_admin_0_countries.geojson",
}


def _download(dest: Path, url: str) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  ✓ {dest.relative_to(APP_DIR)} (cached)")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, 4):
        try:
            print(f"  ↓ {url}")
            req = urllib.request.Request(url, headers={"User-Agent": "energy-map/1.0"})
            with urllib.request.urlopen(req, timeout=90) as r:
                dest.write_bytes(r.read())
            print(f"  ✓ {dest.relative_to(APP_DIR)} ({dest.stat().st_size // 1024} KB)")
            return
        except Exception as exc:  # noqa: BLE001
            print(f"    retry {attempt}/3 ({exc})", file=sys.stderr)
            time.sleep(3)
    raise SystemExit(f"Could not download {url} — check your connection and retry.")


def _valid(code: str) -> bool:
    return code in ISO3_ALPHA3


def compute_routes(flows: list[dict]) -> list[dict]:
    """Attribute trade flows to transit routes (geographic heuristic).

    A flow matches a route when its (exporter, importer) pair satisfies any of
    the route's rules. Both endpoints are credited as "users". Share = a
    country's value on the route / its total trade (exports+imports) in the
    applicable commodity. Everything here is a model estimate.
    """
    from collections import defaultdict
    all_keys = [c[0] for c in COMMODITIES]
    flows_by_c = defaultdict(list)
    totals = {k: {} for k in all_keys}          # per-commodity country totals (exp+imp)
    for f in flows:
        if f["c"] not in totals:
            continue
        flows_by_c[f["c"]].append(f)
        for iso in (f["o"], f["d"]):
            totals[f["c"]][iso] = totals[f["c"]].get(iso, 0) + f["v"]

    out = []
    for r in ROUTES:
        subrules = [
            {"exp": set(sr["exp"]) if sr["exp"] else None,
             "imp": set(sr["imp"]) if sr["imp"] else None}
            for sr in r["rules"]
        ]

        def matches(o, d, _subrules=subrules):
            for sr in _subrules:
                if (sr["exp"] is None or o in sr["exp"]) and \
                   (sr["imp"] is None or d in sr["imp"]):
                    return True
            return False

        # Straits/canals carry any commodity; pipelines carry crude only.
        route_keys = ["crude"] if r["type"] == "pipeline" else all_keys
        stats = {}
        for c in route_keys:
            total_v = total_q = 0.0
            usage, uq, n = {}, {}, 0
            for f in flows_by_c.get(c, ()):
                if not matches(f["o"], f["d"]):
                    continue
                n += 1
                total_v += f["v"]
                if f["q"]:
                    total_q += f["q"]
                for iso in (f["o"], f["d"]):
                    usage[iso] = usage.get(iso, 0) + f["v"]
                    if f["q"]:
                        uq[iso] = uq.get(iso, 0) + f["q"]
            if total_v == 0:
                continue
            users = [{
                "iso": iso, "value": round(v),
                "quantity": round(uq[iso]) if uq.get(iso) else None,
                "share": round(v / totals[c][iso], 4) if totals[c].get(iso) else None,
            } for iso, v in sorted(usage.items(), key=lambda x: -x[1])[:10]]
            stats[c] = {"total": round(total_v),
                        "quantity": round(total_q) if total_q else None,
                        "n_flows": n, "users": users}

        keep = ("id", "name", "type", "commodities", "from", "to",
                "chokepoints", "transit_countries", "transit_time", "note",
                "choke", "path")
        out.append({**{k: r[k] for k in keep}, "stats": stats})
    return out


def build_bundle(conn) -> dict:
    countries: dict[str, dict] = {}

    def slot(iso: str) -> dict:
        return countries.setdefault(iso, {"exp": {}, "imp": {}, "prod": {}})

    # Exports / imports per country per commodity (resolved flow view).
    for row in conn.execute(
        "SELECT reporter_iso, partner_iso, hs_code, "
        "       SUM(trade_value_usd) v FROM export_flows_latest "
        "GROUP BY reporter_iso, partner_iso, hs_code"
    ):
        c = TRADE.get(row["hs_code"])
        if not c:
            continue
        exp, imp = row["reporter_iso"], row["partner_iso"]
        if _valid(exp):
            e = slot(exp)["exp"]; e[c] = e.get(c, 0) + (row["v"] or 0)
        if _valid(imp):
            m = slot(imp)["imp"]; m[c] = m.get(c, 0) + (row["v"] or 0)

    # Production per country per commodity (EIA + USGS, latest available).
    for row in conn.execute(
        "SELECT country_iso, commodity, volume FROM production_latest"
    ):
        if row["commodity"] in PROD_KEYS and _valid(row["country_iso"]):
            slot(row["country_iso"])["prod"][row["commodity"]] = row["volume"] or 0

    # Flow list for the arcs (valid endpoints only).
    flows = []
    for row in conn.execute(
        "SELECT reporter_iso o, partner_iso d, hs_code, year, "
        "       trade_value_usd v, quantity q, quantity_unit u, flow_source s "
        "FROM export_flows_latest"
    ):
        c = TRADE.get(row["hs_code"])
        if not c or not _valid(row["o"]) or not _valid(row["d"]) or not row["v"]:
            continue
        flows.append({
            "o": row["o"], "d": row["d"], "c": c,
            "v": round(row["v"]), "q": row["q"], "u": row["u"],
            "s": row["s"], "y": row["year"],
        })
    flows.sort(key=lambda f: -f["v"])
    n_paths = compute_sea_paths(flows)
    print(f"  sea routes computed: {n_paths}")

    # Per-country coastal port node = where its sea routes touch the coast
    # (the searoute snap). Routes connect here; production sites link to it.
    def _wrap(lon):
        return round(((lon + 540) % 360) - 180, 2)
    ports = {}
    for f in flows:  # sorted by value → each country's port from its biggest flow
        p = f.get("path")
        if not p:
            continue
        ports.setdefault(f["o"], [_wrap(p[0][0]), round(p[0][1], 2)])
        ports.setdefault(f["d"], [_wrap(p[-1][0]), round(p[-1][1], 2)])

    years = sorted({f["y"] for f in flows}, reverse=True)
    registry = [{"key": k, "hs": hs, "label": lbl, "group": grp,
                 "color": col, "prod": pc, "unit": u,
                 "phase": "energy" if grp == "Energy" else
                          ("ore" if "ore" in grp else "refined")}
                for k, hs, lbl, grp, col, pc, u in COMMODITIES]
    # World production per commodity in TONNES — denominator for facility share.
    # USGS units vary (metric tons vs thousand metric tons), so convert.
    prod_world = {}
    for row in conn.execute("SELECT commodity, volume, unit FROM production_latest"):
        v = row["volume"] or 0
        if "thousand" in (row["unit"] or "").lower():
            v *= 1000
        prod_world[row["commodity"]] = prod_world.get(row["commodity"], 0) + v
    port_city_path = config.DATA_DIR / "port_cities.json"
    port_city = json.loads(port_city_path.read_text()) if port_city_path.exists() else {}
    return {
        "meta": {
            "years": years,
            "commodities": registry,
            "prod_world": prod_world,
            "port_city": port_city,
            "n_flows": len(flows),
            "n_countries": len(countries),
            "note": "Flows resolved latest-year-first (2025>2024), direct report "
                    "preferred over mirror. Mirror = reconstructed from importer "
                    "reports; its value is CIF (incl. freight) vs FOB for direct. "
                    "Metal production is USGS mine production (metric tons of "
                    "contained metal). Transit routes attribute flows to "
                    "chokepoints by geography (model estimate) for every "
                    "commodity; oil pipelines carry crude only.",
        },
        "countries": countries,
        "flows": flows,
        "ports": ports,
        "routes": compute_routes(flows),
        "facilities": build_facilities(conn),
    }


ISO_ALIAS = {"KOS": "XKX", "SDS": "SSD", "SAH": "ESH"}


def load_centroids() -> dict:
    """Rough country centroid (lon, lat) per ISO3 from the vendored geojson."""
    gj = json.loads((PUBLIC / "world.geojson").read_text())
    cent = {}
    for f in gj["features"]:
        iso = f["properties"].get("ADM0_A3")
        iso = ISO_ALIAS.get(iso, iso)
        pts = []

        def walk(g):
            if g and isinstance(g[0], (int, float)):
                pts.append(g)
            else:
                for x in g:
                    walk(x)

        walk(f["geometry"]["coordinates"])
        if pts:
            cent[iso] = [sum(p[0] for p in pts) / len(pts),
                         sum(p[1] for p in pts) / len(pts)]
    return cent


def compute_sea_paths(flows: list[dict], top_per_comm: int = 45) -> int:
    """Attach a real maritime route (list of [lon,lat]) to the top flows of each
    commodity, via searoute. No-op if searoute isn't installed."""
    try:
        import searoute as sr
    except ImportError:
        print("  (searoute not installed — flows drawn as arcs; "
              "pip install searoute for real sea routes)")
        return 0
    from collections import defaultdict
    cent = load_centroids()
    by = defaultdict(list)
    for f in flows:
        by[f["c"]].append(f)
    pairs = set()
    for fl in by.values():
        for f in fl[:top_per_comm]:
            if f["o"] in cent and f["d"] in cent and f["o"] != f["d"]:
                pairs.add((f["o"], f["d"]))

    cache = {}
    for o, d in pairs:
        try:
            coords = sr.searoute(cent[o], cent[d]).geometry["coordinates"]
            step = max(1, len(coords) // 28)          # subsample to keep JSON lean
            path = [[round(c[0], 2), round(c[1], 2)] for c in coords[::step]]
            if path[-1] != [round(coords[-1][0], 2), round(coords[-1][1], 2)]:
                path.append([round(coords[-1][0], 2), round(coords[-1][1], 2)])
            cache[(o, d)] = path
        except Exception:
            cache[(o, d)] = None
    for f in flows:
        p = cache.get((f["o"], f["d"]))
        if p:
            f["path"] = p
    return sum(1 for v in cache.values() if v)


def build_facilities(conn) -> list[dict]:
    from collections import defaultdict
    rows = [dict(r) for r in conn.execute(
        "SELECT name, type, country_iso, lat, lon, commodity, operator_company, "
        "       production_volume, production_year, capacity, unit, status, "
        "       start_date, photo_url, photo_source, id, source FROM facility")]
    # Per commodity, prefer Wikidata (operator + photo + global coverage) over
    # the MRDS candidate list; fall back to whatever exists otherwise.
    by_c = defaultdict(list)
    for r in rows:
        by_c[r["commodity"]].append(r)
    out = []
    for fl in by_c.values():
        # Prefer researched flagship producers (correct list + volume + Africa),
        # then Wikidata (photos), then MRDS/GEM fallback.
        pref = ([r for r in fl if r["source"] == "Research"]
                or [r for r in fl if r["source"] == "Wikidata"] or fl)
        for r in pref:
            url = r["id"] if str(r["id"]).startswith("http") else None
            out.append({
                "name": r["name"], "type": r["type"], "iso": r["country_iso"],
                "lat": round(r["lat"], 3), "lon": round(r["lon"], 3),
                "c": r["commodity"], "op": r["operator_company"],
                "cap": r["capacity"], "unit": r["unit"], "prod": r["production_volume"],
                "year": r["production_year"], "status": r["status"], "start": r["start_date"],
                "photo": r["photo_url"], "psrc": r["photo_source"],
                "url": url, "src": r["source"],
            })
    return out


def main() -> None:
    print("Vendoring static assets:")
    for dest, url in ASSETS.items():
        _download(dest, url)

    print("Building data bundle:")
    conn = db.get_connection()
    db.init_db(conn)
    bundle = build_bundle(conn)
    conn.close()

    out = PUBLIC / "data.json"
    out.write_text(json.dumps(bundle, separators=(",", ":")))
    m = bundle["meta"]
    print(f"  ✓ data.json — {m['n_flows']} flows, {m['n_countries']} countries, "
          f"{len(m['commodities'])} commodities, years {m['years']}")
    if not bundle["flows"]:
        print("  ! No flows found. Run the pipeline first: "
              "python data-pipeline/run_all.py --years 2025 2024", file=sys.stderr)


if __name__ == "__main__":
    main()
