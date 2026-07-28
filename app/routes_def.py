"""Curated dataset of the world's major oil & LNG transit routes.

Geometry + reference metadata are hand-authored from public sources (EIA World
Oil Transit Chokepoints, operator data). The *usage* attribution (which trade
flows transit each route) is a GEOGRAPHIC HEURISTIC, not ship-level tracking:
a flow is assigned to a route when its exporter/importer pair matches the
route's rule. Flows can transit several sequential chokepoints (e.g. a Gulf->
Japan cargo crosses both Hormuz and Malacca), which is correct — those are
different chokepoints on one voyage. Alternative routings (Suez vs Cape for
Gulf->Europe) are split by rule so they don't both claim the same leg.

Every usage figure shown in the UI is a model estimate and is tagged as such.
"""

# --- Region sets (ISO3) -----------------------------------------------------
GULF = ["SAU", "IRN", "IRQ", "KWT", "ARE", "QAT", "BHR"]
EAST_ASIA = ["CHN", "JPN", "KOR", "TWN", "PHL", "THA", "VNM", "SGP", "MYS",
             "IDN", "HKG"]
EUROPE = ["DEU", "FRA", "NLD", "ESP", "ITA", "GBR", "POL", "GRC", "BEL", "PRT",
          "SWE", "FIN", "DNK", "LTU", "LVA", "EST", "IRL", "ROU", "BGR", "HRV",
          "SVN", "MLT", "CYP", "AUT", "CZE", "SVK", "HUN", "NOR"]
MED = ["ESP", "FRA", "ITA", "GRC", "TUR", "EGY", "DZA", "LBY", "TUN", "MAR",
       "HRV", "SVN", "MLT", "CYP", "LBN", "ISR", "SYR"]
AMERICAS = ["USA", "CAN", "BRA", "MEX", "CHL", "PER", "ARG", "COL", "ECU",
            "VEN", "TTO", "PAN", "URY", "DOM", "CUB"]
WEST_AFRICA = ["NGA", "AGO", "GHA", "COG", "GAB", "GNQ", "CMR", "CIV", "SEN",
               "MRT", "COD"]
BLACK_SEA_EXP = ["RUS", "KAZ", "AZE", "GEO", "UKR", "ROU", "BGR"]
BALTIC_IMP = EUROPE
# Broader geographic regions so routes work for metals too (not just oil).
S_AMERICA = ["BRA", "ARG", "CHL", "PER", "ECU", "COL", "VEN", "URY", "BOL",
             "GUY", "SUR", "PRY", "TTO"]
S_ASIA = ["IND", "PAK", "BGD", "LKA", "MMR", "NPL"]
OCEANIA = ["AUS", "NZL", "PNG", "NCL", "FJI"]
E_AFRICA = ["ZAF", "MOZ", "TZA", "KEN", "MDG", "NAM", "AGO"]
BALTIC_EXP = ["RUS", "FIN", "SWE", "EST", "LVA", "LTU", "POL"]

# --- Routes -----------------------------------------------------------------
# rules: list of sub-rules; a flow matches if ANY sub-rule matches.
#   exp = allowed exporters (None = any), imp = allowed importers (None = any).
# path: [lon, lat] waypoints (schematic). choke: [lon, lat] label anchor.
ROUTES = [
    {
        "id": "hormuz", "name": "Strait of Hormuz", "type": "strait",
        "commodities": ["crude", "lng"],
        "from": "Persian Gulf terminals (Ras Tanura, Kharg, Ras Laffan)",
        "to": "Gulf of Oman → Indian Ocean",
        "chokepoints": ["Strait of Hormuz (≈33 km wide)"],
        "transit_countries": ["IRN", "OMN", "ARE"],
        "transit_time": "Gulf → open sea: ~1 day through the strait",
        "note": "The world's most critical oil chokepoint; the only sea route "
                "out of the Persian Gulf.",
        "choke": [56.3, 26.6],
        "path": [[50.3, 28.9], [52.5, 27.5], [56.3, 26.6], [58.6, 24.3]],
        "rules": [{"exp": GULF, "imp": None}],
    },
    {
        "id": "malacca", "name": "Strait of Malacca", "type": "strait",
        "commodities": ["crude", "lng"],
        "from": "Indian Ocean (Middle East / Africa)",
        "to": "South China Sea → East Asia",
        "chokepoints": ["Strait of Malacca", "Singapore Strait"],
        "transit_countries": ["IDN", "MYS", "SGP", "THA"],
        "transit_time": "Gulf → China: ~18–22 days total voyage",
        "note": "Shortest sea route between the Gulf/Africa and East Asia; "
                "~2.7 km at its narrowest.",
        "choke": [100.4, 2.5],
        "path": [[80, 8], [95, 6], [98.5, 4], [100.4, 2.5], [103.8, 1.3], [106, 4]],
        "rules": [{"exp": GULF + WEST_AFRICA + EUROPE + MED + S_ASIA + E_AFRICA,
                   "imp": EAST_ASIA}],
    },
    {
        "id": "suez", "name": "Suez Canal & SUMED", "type": "canal",
        "commodities": ["crude", "lng"],
        "from": "Red Sea (Gulf via Bab-el-Mandeb)",
        "to": "Mediterranean → Europe",
        "chokepoints": ["Suez Canal", "SUMED pipeline (bypass)"],
        "transit_countries": ["EGY"],
        "transit_time": "Canal transit ~12–16 h; Gulf → NW Europe ~15 days",
        "note": "Two-way Gulf/Asia ↔ Europe artery for crude and LNG.",
        "choke": [32.55, 30.6],
        "path": [[43, 13], [38, 20], [34.5, 28], [32.55, 30.6], [31.5, 33], [28, 34]],
        "rules": [{"exp": GULF + S_ASIA + EAST_ASIA, "imp": EUROPE + MED},
                  {"exp": EUROPE + MED, "imp": GULF + S_ASIA + EAST_ASIA},
                  {"exp": ["USA", "CAN"], "imp": EAST_ASIA}],
    },
    {
        "id": "bab", "name": "Bab-el-Mandeb", "type": "strait",
        "commodities": ["crude", "lng"],
        "from": "Gulf of Aden",
        "to": "Red Sea → Suez",
        "chokepoints": ["Bab-el-Mandeb (≈29 km wide)"],
        "transit_countries": ["YEM", "DJI", "ERI"],
        "transit_time": "Feeds the Suez route; ~1 day",
        "note": "Red Sea gateway; pairs with Suez. Disruriptions here reroute "
                "traffic around the Cape.",
        "choke": [43.3, 12.6],
        "path": [[47, 13], [45, 12.5], [43.3, 12.6], [41, 15], [38.5, 20]],
        "rules": [{"exp": GULF + S_ASIA, "imp": EUROPE + MED},
                  {"exp": EUROPE + MED, "imp": GULF}],
    },
    {
        "id": "cape", "name": "Cape of Good Hope", "type": "cape",
        "commodities": ["crude", "lng"],
        "from": "West Africa / Gulf (VLCCs too large for Suez)",
        "to": "Europe, Americas, or East Asia",
        "chokepoints": ["Cape of Good Hope (open water, no toll)"],
        "transit_countries": ["ZAF"],
        "transit_time": "Gulf → NW Europe via Cape: ~26 days",
        "note": "Toll-free deep-water alternative when tankers are too large "
                "for Suez or when the Red Sea is avoided.",
        "choke": [19.5, -34.8],
        "path": [[13, -8], [12, -22], [16, -33], [19.5, -34.8], [27, -35], [34, -28]],
        "rules": [{"exp": GULF, "imp": AMERICAS},
                  {"exp": WEST_AFRICA + E_AFRICA + S_AMERICA, "imp": EAST_ASIA + S_ASIA},
                  {"exp": EAST_ASIA, "imp": S_AMERICA + E_AFRICA}],
    },
    {
        "id": "panama", "name": "Panama Canal", "type": "canal",
        "commodities": ["crude", "lng"],
        "from": "US Gulf / Atlantic",
        "to": "Pacific → East Asia, West coast Americas",
        "chokepoints": ["Panama Canal (Neopanamax locks)"],
        "transit_countries": ["PAN"],
        "transit_time": "Canal transit ~8–10 h; US Gulf → Japan ~25 days",
        "note": "Key for US LNG and crude heading to Asia and the Pacific "
                "coast; capacity-constrained for LNG carriers.",
        "choke": [-79.7, 9.1],
        "path": [[-90, 20], [-81, 12], [-79.7, 9.3], [-79.9, 8.5], [-84, 5], [-100, 10]],
        "rules": [{"exp": ["USA", "CAN", "MEX", "TTO", "COL", "VEN", "BRA"],
                   "imp": EAST_ASIA},
                  {"exp": EAST_ASIA, "imp": ["CHL", "PER", "ECU", "COL"]}],
    },
    {
        "id": "turkish", "name": "Turkish Straits", "type": "strait",
        "commodities": ["crude", "lng"],
        "from": "Black Sea (Novorossiysk, Ceyhan feed)",
        "to": "Mediterranean → world",
        "chokepoints": ["Bosphorus (≈0.7 km wide)", "Dardanelles"],
        "transit_countries": ["TUR"],
        "transit_time": "Straits transit ~1 day; frequent congestion delays",
        "note": "Sole outlet for Black Sea oil exports (Russia, Kazakhstan, "
                "Azerbaijan).",
        "choke": [29.0, 41.1],
        "path": [[37.8, 44.6], [33, 42.5], [29.1, 41.1], [26.4, 40.1], [24, 38]],
        "rules": [{"exp": BLACK_SEA_EXP, "imp": None}],
    },
    {
        "id": "danish", "name": "Danish Straits", "type": "strait",
        "commodities": ["crude", "lng"],
        "from": "Russian Baltic (Primorsk, Ust-Luga)",
        "to": "North Sea → Atlantic",
        "chokepoints": ["Great Belt", "Øresund"],
        "transit_countries": ["DNK", "SWE"],
        "transit_time": "~1 day through the straits",
        "note": "Exit for Russian Baltic crude exports into the North Sea.",
        "choke": [11.0, 56.0],
        "path": [[28.7, 59.9], [22, 59.3], [15, 55.6], [11, 56], [8, 57.2]],
        "rules": [{"exp": BALTIC_EXP,
                   "imp": AMERICAS + EAST_ASIA + WEST_AFRICA + S_ASIA}],
    },
    {
        "id": "gibraltar", "name": "Strait of Gibraltar", "type": "strait",
        "commodities": ["crude", "lng"],
        "from": "Atlantic / West Africa / US",
        "to": "Mediterranean",
        "chokepoints": ["Strait of Gibraltar (≈14 km wide)"],
        "transit_countries": ["ESP", "MAR", "GBR"],
        "transit_time": "Gateway to the Mediterranean; ~hours",
        "note": "Atlantic ↔ Mediterranean gateway for cargoes into Southern "
                "Europe.",
        "choke": [-5.6, 35.95],
        "path": [[-15, 33], [-9, 36], [-5.6, 35.95], [-1, 36.5], [4, 38]],
        "rules": [{"exp": WEST_AFRICA + S_AMERICA + ["USA", "CAN"], "imp": MED},
                  {"exp": MED, "imp": ["USA", "CAN"] + S_AMERICA},
                  {"exp": ["RUS"], "imp": MED}],
    },
    {
        "id": "lombok", "name": "Lombok Strait", "type": "strait",
        "commodities": ["crude", "lng"],
        "from": "Indian Ocean (deep-draft VLCCs)",
        "to": "Makassar Strait → East Asia",
        "chokepoints": ["Lombok Strait", "Makassar Strait"],
        "transit_countries": ["IDN"],
        "transit_time": "Alternative to Malacca; adds ~3 days",
        "note": "Deep-water bypass to Malacca for the largest tankers bound "
                "for East Asia.",
        "choke": [115.9, -8.7],
        "path": [[100, -6], [110, -8], [115.9, -8.7], [117.5, -4], [119, 2]],
        "rules": [{"exp": GULF + S_ASIA + E_AFRICA, "imp": ["CHN", "JPN", "KOR", "TWN"]}],
    },
    # --- Oil pipelines (crude only) ----------------------------------------
    {
        "id": "druzhba", "name": "Druzhba Pipeline", "type": "pipeline",
        "commodities": ["crude"],
        "from": "Russia (Volga-Urals / Western Siberia)",
        "to": "Central & Eastern Europe",
        "chokepoints": ["Mozyr junction (Belarus)"],
        "transit_countries": ["RUS", "BLR", "UKR", "POL"],
        "transit_time": "Pipeline flow (continuous)",
        "note": "One of the world's longest oil pipelines; supplies refineries "
                "in Central Europe. (Pipeline crude, not seaborne.)",
        "choke": [23.5, 52.1],
        "path": [[52, 55], [44, 54], [35, 53], [27, 52.5], [23.5, 52.1], [18, 50]],
        "rules": [{"exp": ["RUS", "KAZ"], "imp": ["POL", "DEU", "HUN", "SVK",
                                                  "CZE", "BLR", "AUT"]}],
    },
    {
        "id": "espo", "name": "ESPO Pipeline", "type": "pipeline",
        "commodities": ["crude"],
        "from": "Eastern Siberia (Taishet)",
        "to": "Pacific (Kozmino) & China (Daqing spur)",
        "chokepoints": ["Kozmino terminal", "Mohe (China spur)"],
        "transit_countries": ["RUS", "CHN"],
        "transit_time": "Pipeline flow (continuous)",
        "note": "Carries East Siberian crude to Pacific markets and directly "
                "to China.",
        "choke": [131, 43.1],
        "path": [[98, 56], [110, 53], [120, 50], [128, 46], [131, 43.1]],
        "rules": [{"exp": ["RUS"], "imp": ["CHN", "JPN", "KOR"]}],
    },
    {
        "id": "cpc", "name": "Caspian Pipeline (CPC)", "type": "pipeline",
        "commodities": ["crude"],
        "from": "Kazakhstan (Tengiz, Kashagan)",
        "to": "Black Sea (Novorossiysk) → world",
        "chokepoints": ["Novorossiysk marine terminal"],
        "transit_countries": ["KAZ", "RUS"],
        "transit_time": "Pipeline to port, then seaborne",
        "note": "Kazakhstan's main crude export route; feeds the Turkish "
                "Straits onward.",
        "choke": [37.9, 44.7],
        "path": [[53, 46.5], [48, 46], [42, 45], [37.9, 44.7]],
        "rules": [{"exp": ["KAZ"], "imp": EUROPE + MED}],
    },
    {
        "id": "btc", "name": "Baku–Tbilisi–Ceyhan (BTC)", "type": "pipeline",
        "commodities": ["crude"],
        "from": "Azerbaijan (Sangachal, Baku)",
        "to": "Mediterranean (Ceyhan, Turkey)",
        "chokepoints": ["Ceyhan marine terminal"],
        "transit_countries": ["AZE", "GEO", "TUR"],
        "transit_time": "Pipeline to port, then seaborne",
        "note": "Routes Caspian crude to the Mediterranean, bypassing the "
                "Turkish Straits.",
        "choke": [35.8, 36.9],
        "path": [[49.8, 40.4], [44.8, 41.7], [40, 39], [35.8, 36.9]],
        "rules": [{"exp": ["AZE", "KAZ"], "imp": EUROPE + MED}],
    },
    {
        "id": "keystone", "name": "Keystone Pipeline", "type": "pipeline",
        "commodities": ["crude"],
        "from": "Alberta oil sands (Canada)",
        "to": "US Midwest & Gulf Coast",
        "chokepoints": ["Cushing, Oklahoma hub"],
        "transit_countries": ["CAN", "USA"],
        "transit_time": "Pipeline flow (continuous)",
        "note": "Primary conduit for Canadian crude into the US market.",
        "choke": [-97, 44],
        "path": [[-112, 54], [-104, 49], [-97, 44], [-96, 39], [-95, 33]],
        "rules": [{"exp": ["CAN"], "imp": ["USA"]}],
    },
]
