"""Build companies.json for the Companies section: curated profiles of the
major oil companies and commodity trading houses, their flagship operated
assets (geolocated) and their footprint across the commodities we track.

    python app/build_companies.py

Scope note: `assets` is a curated set of *flagship* operated assets (not an
exhaustive inventory) — enough to show each company's global footprint and where
it sits in each commodity. Coordinates are facility/city level. Financials are
latest-reported approximate full-year figures (FY2024 where available); trading
houses are private, so their turnover/volume come from their own releases and
press (Vitol, Trafigura, Glencore, Mercuria 2024 results).

Roles vocabulary: Upstream, Refining, Integrated, LNG, Mining, Smelting,
Trading, Storage & logistics.
Asset types (drive the marker shape): oilfield, offshore, refinery, lng,
terminal, mine, smelter, office.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

PUBLIC = Path(__file__).resolve().parent / "public"


def _load_env():
    """Load .env locally so _SB is detected. In Actions the vars are already
    in the environment (no .env file); setdefault never overrides them."""
    p = Path(__file__).resolve().parent.parent / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v)


_load_env()
# When Supabase is configured, sync the curated companies straight into the DB
# (companies / company_footprint / company_assets) instead of writing JSON.
_SB = os.environ.get("SUPABASE_POOLER_URL") or os.environ.get("SUPABASE_DB_URL")


def _sync_supabase(companies: list[dict]) -> None:
    import psycopg2
    conn = psycopg2.connect(_SB, sslmode="require", connect_timeout=25)
    cur = conn.cursor()
    cur.execute("truncate company_footprint, company_assets;")
    for i, c in enumerate(companies):
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
    conn.commit()
    conn.close()


def A(name, type, commodity, country, lat, lon, note=""):
    return {"name": name, "type": type, "commodity": commodity,
            "country": country, "lat": lat, "lon": lon, "note": note}


def F(commodity, role, presence, note=""):
    return {"commodity": commodity, "role": role, "presence": presence, "note": note}


COMPANIES = [
    # ============================ SUPERMAJORS ============================
    {
        "id": "exxonmobil", "name": "ExxonMobil", "type": "Supermajor",
        "hq": "Spring, Texas · USA", "founded": 1999, "employees": 61000,
        "revenue": "$344B", "listing": "NYSE: XOM", "color": "#E33D3D",
        "blurb": "The largest Western investor-owned oil company — integrated from "
                 "the Permian and Guyana upstream to Gulf Coast refining and chemicals.",
        "footprint": [
            F("crude", "Integrated", 96, "~4.3 Mboe/d output; Permian & Guyana growth engines"),
            F("lng", "LNG production", 68, "PNG LNG, Golden Pass (starting up), Qatar stakes"),
        ],
        "assets": [
            A("Permian Basin", "oilfield", "crude", "USA", 31.86, -102.03, "Largest US shale acreage after Pioneer deal"),
            A("Stabroek Block (Guyana)", "offshore", "crude", "Guyana", 7.6, -56.9, "~650 kbbl/d and rising; Liza / Payara"),
            A("Baytown Refinery & Chemicals", "refinery", "crude", "USA", 29.75, -95.01, "~560 kbbl/d, one of the largest in the US"),
            A("Baton Rouge Refinery", "refinery", "crude", "USA", 30.50, -91.19, "Historic Gulf Coast complex"),
            A("Jurong Island Refinery", "refinery", "crude", "Singapore", 1.27, 103.70, "Integrated refining & petrochemicals hub"),
            A("Rotterdam Refinery", "refinery", "crude", "Netherlands", 51.88, 4.30, "European refining base"),
            A("PNG LNG", "lng", "lng", "Papua New Guinea", -9.44, 147.18, "~8 Mtpa, operated"),
            A("Golden Pass LNG", "lng", "lng", "USA", 29.76, -93.87, "US export terminal ramping up"),
        ],
    },
    {
        "id": "chevron", "name": "Chevron", "type": "Supermajor",
        "hq": "San Ramon, California · USA", "founded": 1879, "employees": 46000,
        "revenue": "$202B", "listing": "NYSE: CVX", "color": "#2C6BE0",
        "blurb": "US supermajor anchored by Kazakhstan's Tengiz, the Permian, and a "
                 "world-leading Australian LNG position.",
        "footprint": [
            F("crude", "Integrated", 92, "~3.3 Mboe/d; Tengiz expansion + Permian"),
            F("lng", "LNG production", 78, "Gorgon & Wheatstone — ~25 Mtpa operated"),
        ],
        "assets": [
            A("Tengiz (TCO)", "oilfield", "crude", "Kazakhstan", 46.00, 53.50, "Giant field; major expansion online"),
            A("Permian Basin", "oilfield", "crude", "USA", 31.86, -102.03, "Core US shale growth"),
            A("Gorgon LNG", "lng", "lng", "Australia", -20.80, 115.50, "~15.6 Mtpa on Barrow Island"),
            A("Wheatstone LNG", "lng", "lng", "Australia", -21.68, 115.10, "~8.9 Mtpa, operated"),
            A("Pascagoula Refinery", "refinery", "crude", "USA", 30.36, -88.56, "~330 kbbl/d Gulf Coast"),
            A("Richmond Refinery", "refinery", "crude", "USA", 37.94, -122.39, "California supply"),
            A("Escravos", "offshore", "crude", "Nigeria", 5.60, 5.20, "Niger Delta operations"),
        ],
    },
    {
        "id": "shell", "name": "Shell", "type": "Supermajor",
        "hq": "London · United Kingdom", "founded": 1907, "employees": 96000,
        "revenue": "$284B", "listing": "LSE / NYSE: SHEL", "color": "#EBC12E",
        "blurb": "The world's largest LNG trader — integrated gas, deep-water crude "
                 "and Europe's biggest refinery-chemicals park at Rotterdam.",
        "footprint": [
            F("lng", "Integrated + Trading", 96, "~65 Mtpa handled; #1 LNG portfolio"),
            F("crude", "Integrated", 88, "~1.8 Mbbl/d liquids; Gulf of Mexico deep water"),
        ],
        "assets": [
            A("Energy & Chemicals Park Rotterdam (Pernis)", "refinery", "crude", "Netherlands", 51.88, 4.39, "Largest refinery in Europe"),
            A("Prelude FLNG", "lng", "lng", "Australia", -13.80, 123.30, "World's largest floating LNG facility"),
            A("Pearl GTL", "lng", "lng", "Qatar", 25.90, 51.53, "Largest gas-to-liquids plant"),
            A("Queensland Curtis LNG", "lng", "lng", "Australia", -23.76, 151.20, "Coal-seam-gas LNG at Gladstone"),
            A("Nigeria LNG (Bonny)", "lng", "lng", "Nigeria", 4.42, 7.15, "Major stake, Bonny Island"),
            A("Perdido (Gulf of Mexico)", "offshore", "crude", "USA", 26.13, -94.90, "Deep-water hub"),
            A("Bukom Refinery", "refinery", "crude", "Singapore", 1.22, 103.75, "Asia manufacturing site"),
        ],
    },
    {
        "id": "bp", "name": "BP", "type": "Supermajor",
        "hq": "London · United Kingdom", "founded": 1909, "employees": 88000,
        "revenue": "$193B", "listing": "LSE / NYSE: BP", "color": "#3AA657",
        "blurb": "UK supermajor with a large trading arm, Azerbaijan and Gulf of "
                 "Mexico crude, and LNG from Tangguh and beyond.",
        "footprint": [
            F("crude", "Integrated", 86, "~2.3 Mboe/d; Azerbaijan, GoM, Middle East"),
            F("lng", "Production + Trading", 72, "Tangguh, Freeport offtake; active LNG trading"),
        ],
        "assets": [
            A("Whiting Refinery", "refinery", "crude", "USA", 41.68, -87.49, "~440 kbbl/d, BP's largest refinery"),
            A("Azeri-Chirag-Gunashli / Shah Deniz", "offshore", "crude", "Azerbaijan", 40.00, 50.50, "Caspian crude & gas complex"),
            A("Thunder Horse (Gulf of Mexico)", "offshore", "crude", "USA", 28.19, -88.49, "Deep-water platform"),
            A("Tangguh LNG", "lng", "lng", "Indonesia", -2.40, 133.50, "~11.4 Mtpa in Papua"),
            A("Rotterdam Refinery", "refinery", "crude", "Netherlands", 51.88, 4.29, "European refining"),
            A("Gelsenkirchen Refinery", "refinery", "crude", "Germany", 51.57, 7.05, "Ruhr petrochemicals"),
            A("Castellón Refinery", "refinery", "crude", "Spain", 39.98, 0.02, "Mediterranean supply"),
        ],
    },
    {
        "id": "totalenergies", "name": "TotalEnergies", "type": "Supermajor",
        "hq": "Courbevoie (Paris) · France", "founded": 1924, "employees": 103000,
        "revenue": "$195B", "listing": "Euronext / NYSE: TTE", "color": "#E2483C",
        "blurb": "French supermajor with one of the broadest LNG portfolios — Yamal, "
                 "Mozambique, US and Middle East — plus African upstream.",
        "footprint": [
            F("lng", "Integrated + Trading", 90, "~40+ Mtpa portfolio; global regas access"),
            F("crude", "Integrated", 84, "~2.4 Mboe/d; Africa, Middle East, US"),
        ],
        "assets": [
            A("Antwerp Refinery & Platform", "refinery", "crude", "Belgium", 51.24, 4.30, "Second-largest EU refinery-petchem site"),
            A("Normandy Platform (Gonfreville)", "refinery", "crude", "France", 49.49, 0.24, "Largest French refining site"),
            A("Port Arthur Refinery", "refinery", "crude", "USA", 29.87, -93.93, "US Gulf Coast"),
            A("Yamal LNG", "lng", "lng", "Russia", 71.27, 72.06, "Arctic LNG stake, Sabetta"),
            A("Mozambique LNG", "lng", "lng", "Mozambique", -10.90, 40.60, "~13 Mtpa (restarting), Afungi"),
            A("Ichthys LNG", "lng", "lng", "Australia", -12.46, 130.84, "Darwin, stake"),
            A("Lake Albert / EACOP", "oilfield", "crude", "Uganda", 1.70, 31.10, "Onshore crude + export pipeline"),
        ],
    },
    {
        "id": "conocophillips", "name": "ConocoPhillips", "type": "Supermajor",
        "hq": "Houston, Texas · USA", "founded": 2002, "employees": 11800,
        "revenue": "$59B", "listing": "NYSE: COP", "color": "#C0392B",
        "blurb": "The largest independent pure-play upstream producer — US shale at "
                 "scale, Alaska, and Australian LNG. No refining.",
        "footprint": [
            F("crude", "Upstream", 90, "~1.9 Mboe/d; Permian, Eagle Ford, Bakken, Alaska"),
            F("lng", "LNG production", 55, "Australia Pacific LNG; US offtake"),
        ],
        "assets": [
            A("Permian / Delaware Basin", "oilfield", "crude", "USA", 31.86, -103.50, "Core Lower-48 shale (Concho, Marathon)"),
            A("Eagle Ford", "oilfield", "crude", "USA", 28.80, -98.50, "South Texas shale"),
            A("Bakken", "oilfield", "crude", "USA", 47.80, -103.00, "North Dakota shale"),
            A("Willow / Alaska North Slope", "oilfield", "crude", "USA", 70.25, -148.30, "Arctic development"),
            A("Surmont Oil Sands", "oilfield", "crude", "Canada", 55.60, -110.90, "Alberta SAGD, now 100%-owned"),
            A("Australia Pacific LNG", "lng", "lng", "Australia", -23.84, 151.26, "Gladstone, major stake"),
            A("Ekofisk (North Sea)", "offshore", "crude", "Norway", 56.55, 3.21, "Long-life North Sea hub"),
        ],
    },
    {
        "id": "eni", "name": "Eni", "type": "Supermajor",
        "hq": "Rome · Italy", "founded": 1953, "employees": 33000,
        "revenue": "$100B", "listing": "BIT / NYSE: E", "color": "#F2C230",
        "blurb": "Italy's integrated major — an exploration-led upstream across "
                 "Africa and the Mediterranean, with fast-tracked gas and LNG.",
        "footprint": [
            F("crude", "Integrated", 80, "~1.7 Mboe/d; Africa, Kazakhstan, Middle East"),
            F("lng", "Production + Trading", 70, "Egypt, Mozambique, Congo LNG"),
        ],
        "assets": [
            A("Zohr Gas Field", "offshore", "lng", "Egypt", 33.70, 32.50, "Giant Mediterranean gas field"),
            A("Coral South FLNG", "lng", "lng", "Mozambique", -10.90, 40.60, "Floating LNG, Rovuma"),
            A("Congo LNG", "lng", "lng", "Congo", -4.80, 11.80, "Fast-tracked FLNG"),
            A("Kashagan", "offshore", "crude", "Kazakhstan", 46.30, 51.50, "Giant Caspian field, stake"),
            A("Val d'Agri", "oilfield", "crude", "Italy", 40.40, 15.90, "Largest onshore field in the EU"),
            A("Sannazzaro Refinery", "refinery", "crude", "Italy", 45.10, 8.90, "Northern Italy refining"),
            A("Block 15/06", "offshore", "crude", "Angola", -8.00, 12.00, "Deep-water Angola"),
        ],
    },

    # ========================= TRADING HOUSES =========================
    {
        "id": "vitol", "name": "Vitol", "type": "Trading house",
        "hq": "Geneva · Switzerland / Rotterdam", "founded": 1966, "employees": 1600,
        "revenue": "$331B", "listing": "Private", "color": "#F4A93C",
        "blurb": "The world's largest independent energy trader — ~7.2 Mbbl/d of "
                 "crude and products, backed by the VTTI storage network.",
        "footprint": [
            F("crude", "Trading", 98, "~7.2 Mbbl/d crude & products traded (2024)"),
            F("lng", "Trading", 74, "Growing LNG book and regas access"),
            F("aluminium", "Trading", 40, "Building a base-metals desk to rival the majors"),
        ],
        "assets": [
            A("Vitol (Geneva HQ)", "office", "crude", "Switzerland", 46.20, 6.14, "Trading headquarters"),
            A("Vitol Singapore", "office", "crude", "Singapore", 1.28, 103.85, "Asia trading hub"),
            A("Vitol Houston", "office", "crude", "USA", 29.76, -95.37, "Americas trading"),
            A("VTTI Rotterdam (ATB)", "terminal", "crude", "Netherlands", 51.90, 4.28, "Storage & blending"),
            A("VTTI Fujairah", "terminal", "crude", "United Arab Emirates", 25.15, 56.35, "Middle East bunkering & storage"),
            A("VTTI Antwerp", "terminal", "crude", "Belgium", 51.29, 4.32, "NW Europe products terminal"),
            A("Cape Three Points (upstream)", "offshore", "crude", "Ghana", 4.90, -2.70, "West Africa upstream, Sankofa"),
        ],
    },
    {
        "id": "trafigura", "name": "Trafigura", "type": "Trading house",
        "hq": "Singapore / Geneva · Switzerland", "founded": 1993, "employees": 13000,
        "revenue": "$243B", "listing": "Private", "color": "#4B7BEC",
        "blurb": "The metals-and-energy trading heavyweight — huge in copper, zinc "
                 "and cobalt through Nyrstar smelters and Impala logistics.",
        "footprint": [
            F("crude", "Trading", 90, "~6.5 Mbbl/d oil & products"),
            F("copper", "Trading + Smelting", 88, "World's largest copper-concentrate trader"),
            F("zinc", "Trading + Smelting", 82, "Nyrstar multi-metals smelters"),
            F("nickel", "Trading + Mining", 55, "Prony Resources, New Caledonia"),
            F("lng", "Trading", 50, "Growing LNG & gas book"),
        ],
        "assets": [
            A("Trafigura (Singapore HQ)", "office", "crude", "Singapore", 1.28, 103.85, "Group headquarters"),
            A("Trafigura Geneva", "office", "crude", "Switzerland", 46.20, 6.14, "European trading hub"),
            A("Nyrstar Port Pirie", "smelter", "zinc", "Australia", -33.19, 138.01, "Multi-metals smelter (lead/zinc/silver)"),
            A("Nyrstar Budel", "smelter", "zinc", "Netherlands", 51.28, 5.59, "Zinc smelter"),
            A("Impala Terminal Callao", "terminal", "copper", "Peru", -12.05, -77.14, "Andean metals export logistics"),
            A("Prony Resources (Goro)", "mine", "nickel", "New Caledonia", -22.30, 167.00, "Nickel-cobalt mine & plant, stake"),
            A("Impala Terminal Burnside", "terminal", "crude", "USA", 30.14, -90.99, "Mississippi River bulk terminal"),
        ],
    },
    {
        "id": "glencore", "name": "Glencore", "type": "Trading house",
        "hq": "Baar · Switzerland", "founded": 1974, "employees": 150000,
        "revenue": "$231B", "listing": "LSE: GLEN", "color": "#5FD9A6",
        "blurb": "The uniquely integrated miner-and-marketer — owns the copper, "
                 "cobalt, zinc and nickel it also trades at global scale.",
        "footprint": [
            F("copper", "Mining + Trading", 94, "Top-tier producer & marketer; DRC, Australia, Chile"),
            F("cobalt", "Mining + Trading", 92, "World's largest cobalt producer (DRC)"),
            F("zinc", "Mining + Trading", 88, "Mount Isa, McArthur River"),
            F("nickel", "Mining + Trading", 66, "Murrin Murrin; global marketing"),
            F("crude", "Trading", 70, "~3.7 Mbbl/d oil & products"),
            F("aluminium", "Trading", 60, "Major aluminium & alumina marketer"),
            F("manganese", "Trading", 45, "Ferroalloys marketing"),
        ],
        "assets": [
            A("Glencore (Baar HQ)", "office", "copper", "Switzerland", 47.19, 8.52, "Group headquarters"),
            A("Mount Isa Mines", "mine", "copper", "Australia", -20.72, 139.49, "Copper & zinc complex"),
            A("Kamoto Copper Company (KCC)", "mine", "copper", "Democratic Republic of the Congo", -10.72, 25.47, "Copper-cobalt, Kolwezi"),
            A("Mutanda Mining", "mine", "cobalt", "Democratic Republic of the Congo", -10.70, 25.50, "One of the world's largest cobalt mines"),
            A("Collahuasi (stake)", "mine", "copper", "Chile", -20.98, -68.75, "High-altitude copper"),
            A("Murrin Murrin", "mine", "nickel", "Australia", -28.70, 121.90, "Nickel-cobalt operation"),
            A("McArthur River Mine", "mine", "zinc", "Australia", -16.43, 136.10, "Major zinc-lead mine"),
            A("Astron Energy Refinery", "refinery", "crude", "South Africa", -33.90, 18.50, "Cape Town refinery"),
        ],
    },
    {
        "id": "gunvor", "name": "Gunvor", "type": "Trading house",
        "hq": "Geneva · Switzerland", "founded": 2000, "employees": 1600,
        "revenue": "$127B", "listing": "Private", "color": "#C77DFF",
        "blurb": "A top-five independent energy trader that also owns refining — "
                 "crude, products, LNG and a growing biofuels book.",
        "footprint": [
            F("crude", "Trading + Refining", 84, "~2.8 Mbbl/d traded; owns two EU refineries"),
            F("lng", "Trading", 60, "Active LNG and natural-gas desks"),
        ],
        "assets": [
            A("Gunvor (Geneva HQ)", "office", "crude", "Switzerland", 46.20, 6.14, "Trading headquarters"),
            A("Gunvor Singapore", "office", "crude", "Singapore", 1.28, 103.85, "Asia trading hub"),
            A("Rotterdam Refinery", "refinery", "crude", "Netherlands", 51.89, 4.29, "Owned refining asset"),
            A("Ingolstadt Refinery", "refinery", "crude", "Germany", 48.77, 11.43, "Bavarian refinery"),
            A("Europoort Terminal", "terminal", "crude", "Netherlands", 51.95, 4.13, "Rotterdam storage"),
            A("Gunvor USA (Stamford)", "office", "crude", "USA", 41.05, -73.54, "Americas trading"),
        ],
    },
    {
        "id": "mercuria", "name": "Mercuria", "type": "Trading house",
        "hq": "Geneva · Switzerland", "founded": 2004, "employees": 1500,
        "revenue": "$130B", "listing": "Private", "color": "#E8794B",
        "blurb": "A fast-growing energy trader diversifying into metals, marine "
                 "fuels and the low-carbon transition.",
        "footprint": [
            F("crude", "Trading", 82, "Global crude & products; $2.09B FY profit"),
            F("lng", "Trading", 58, "Gas & LNG desks"),
            F("copper", "Trading", 48, "Expanding base-metals franchise"),
        ],
        "assets": [
            A("Mercuria (Geneva HQ)", "office", "crude", "Switzerland", 46.20, 6.14, "Group headquarters"),
            A("Mercuria Singapore", "office", "crude", "Singapore", 1.28, 103.85, "Asia trading hub"),
            A("Mercuria Houston", "office", "crude", "USA", 29.76, -95.37, "Americas trading"),
            A("Minerva Bunkering (Piraeus)", "terminal", "crude", "Greece", 37.94, 23.64, "Global marine-fuels supply"),
            A("Vesta Terminals (Vlissingen)", "terminal", "crude", "Netherlands", 51.44, 3.58, "NW Europe storage JV"),
        ],
    },
]

# Agent-researched extras (national oil companies + diversified miners), kept as
# a committed JSON data file so the roster stays exhaustive without a giant
# literal. Merged into the curated list above.
_EXTRA = Path(__file__).resolve().parent / "companies_extra.json"
if _EXTRA.exists():
    COMPANIES = COMPANIES + json.loads(_EXTRA.read_text())


def build() -> dict:
    out = []
    for c in COMPANIES:
        assets = c["assets"]
        countries = sorted({a["country"] for a in assets})
        commodities = [f["commodity"] for f in c["footprint"]]
        out.append({**c,
                    "numAssets": len(assets),
                    "numCountries": len(countries),
                    "commodities": commodities})
    return {"companies": out}


def main() -> None:
    data = build()
    n_assets = sum(c["numAssets"] for c in data["companies"])
    if _SB:
        _sync_supabase(COMPANIES)
        print(f"  ✓ companies → Supabase — {len(COMPANIES)} companies, {n_assets} assets")
        return
    (PUBLIC / "companies.json").write_text(json.dumps(data, separators=(",", ":")))
    print(f"  ✓ companies.json — {len(data['companies'])} companies, {n_assets} assets")


if __name__ == "__main__":
    main()
